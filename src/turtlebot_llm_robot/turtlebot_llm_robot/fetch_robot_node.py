"""
fetch_robot_node

RobotCommand 시퀀스를 goal로 받는 ExecuteSequence 액션 서버
do_search가 카메라 콜백이 계속 갱신하는 self.state를 기다렸다가(블로킹) 결과를 리턴하는 구조.

동시성 구조 (콜백그룹 3개로 분리):
- action_cb_group: execute_callback (시퀀스 실행)
- sensor_cb_group: image_callback (카메라 프레임마다 로봇 움직임 + self.state 갱신)
- emergency_cb_group: emergency_stop_callback (다른 무엇이 실행 중이든 즉시 처리돼야 함)

정책:
- 일반 실패(search not_found, move 실패 등)는 시퀀스 계속 진행
- 비상정지는 예외적으로 시퀀스 전체를 즉시 중단시킴 (남은 액션 폐기)
"""

import time

import cv2
import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from sensor_msgs.msg import CompressedImage
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from cv_bridge import CvBridge
from ultralytics import YOLO

from turtlebot_llm_interfaces.msg import RobotStatus
from turtlebot_llm_interfaces.action import ExecuteSequence

DEFAULT_TIME = 5 
DEFAULT_REPEAT = 1
def get_default_time(action) -> int:
    #time을 생략한 명령에 적용할 기본 지속시간. 회전류는 8초, 나머지는 5초
    if action.type == 'move' and action.dir in ('left', 'right'):
        return 8
    if action.type == 'perform' and action.action in ('spin', 'circle'):
        return 8
    return DEFAULT_TIME
SEARCH_TIMEOUT_SEC = 60.0

LINEAR_SPEED = {'slow': 0.03, 'normal': 0.06, 'fast': 0.12}
ANGULAR_SPEED = {'slow': 0.5, 'normal': 0.8, 'fast': 1.2}


class FetchRobotNode(Node):
    def __init__(self):
        super().__init__('fetch_robot_node')

        # 콜백 그룹 3개
        self.action_cb_group = ReentrantCallbackGroup() # 여러 콜백 동시에 실행 가능
        self.sensor_cb_group = MutuallyExclusiveCallbackGroup() # 여러 콜백 동시에 실행 x
        self.emergency_cb_group = ReentrantCallbackGroup()

        self._action_server = ActionServer(
            self,
            ExecuteSequence,
            'execute_sequence',
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.action_cb_group,
        )

        # YOLO 로드
        self.bridge = CvBridge()
        self.get_logger().info('YOLO 모델 로딩 중...')
        self.model = YOLO('yolov8n.pt')
        self.model.fuse()

        self.image_sub = self.create_subscription( # 구독
            CompressedImage, '/image_raw/compressed', self.image_callback, 1,
            callback_group=self.sensor_cb_group,
        )
        self.emergency_sub = self.create_subscription( # 구독
            Bool, 'emergency_stop', self.emergency_stop_callback, 10,
            callback_group=self.emergency_cb_group,
        )
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10) # 발행

        self.target_class = None
        self.search_generation = 0
        self.state = 'idle'            # 'idle' / 'searching' / 'approaching' / 'arrived'
        self.miss_count = 0
        self.miss_threshold = 10
        self.emergency_stop = False
        self.is_aligning = False

        self.get_logger().info('fetch_robot_node 준비 완료. execute_sequence 액션 서버 대기 중.')

    # 비상정지
    def emergency_stop_callback(self, msg: Bool):
        if msg.data:
            self.emergency_stop = True
            self.cmd_pub.publish(Twist())
            self.get_logger().warn('비상정지 신호 수신 - 즉시 정지')

 
    # 액션 서버 콜백
    def goal_callback(self, goal_request):
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle):
        return CancelResponse.ACCEPT

    def execute_callback(self, goal_handle):
        self.emergency_stop = False  # 새 명령 시작 -> 이전 비상정지 상태 초기화

        actions = goal_handle.request.command.actions
        statuses = []
        success_count = 0
        fail_count = 0

        for i, action in enumerate(actions):
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                return self._build_result(statuses, success_count, fail_count)

            result_str = self.execute_action(action, goal_handle)
            self.cmd_pub.publish(Twist())  # 액션 하나 끝나면 무조건 정지

            status = RobotStatus()
            status.type = action.type
            status.target = action.target
            status.dir = action.dir
            status.action = action.action
            status.result = result_str
            statuses.append(status)

            if result_str == 'success':
                success_count += 1
            else:
                fail_count += 1

            feedback = ExecuteSequence.Feedback()
            feedback.current_index = i
            feedback.total_count = len(actions)
            feedback.status = status
            goal_handle.publish_feedback(feedback)

            if self.emergency_stop:
                self.get_logger().warn('비상정지로 시퀀스 중단 - 남은 액션 폐기')
                self.emergency_stop = False
                goal_handle.abort()
                return self._build_result(statuses, success_count, fail_count)

        goal_handle.succeed()
        return self._build_result(statuses, success_count, fail_count)

    def _build_result(self, statuses, success_count, fail_count):
        result = ExecuteSequence.Result()
        result.statuses = statuses
        result.success_count = success_count
        result.fail_count = fail_count
        return result

    def execute_action(self, action, goal_handle=None) -> str:
        time_s = action.time if action.time != -1 else get_default_time(action)
        repeat = action.repeat if action.repeat != -1 else DEFAULT_REPEAT

        try: # 타입별로 분기
            if action.type == 'search':
                return self.do_search(action.target, goal_handle=goal_handle)
            elif action.type == 'move':
                results = [self.do_move(action.dir, action.speed, time_s) for _ in range(repeat)]
                return 'success' if all(results) else 'fail'
            elif action.type == 'perform':
                results = [self.do_perform(action.action, action.speed, time_s) for _ in range(repeat)]
                return 'success' if all(results) else 'fail'
            elif action.type == 'stop':
                results = [self.do_stop(time_s) for _ in range(repeat)]
                return 'success' if all(results) else 'fail'
            elif action.type == 'resume':
                return 'success' if self.do_resume() else 'fail'
            else:
                self.get_logger().error(f'알 수 없는 액션 타입: {action.type}')
                return 'fail'
        except Exception as e:
            self.get_logger().error(f'액션 실행 중 예외: {e}')
            return 'fail'


    # 하드웨어 액션
    def do_search(self, target: str, goal_handle=None) -> str:

        self.search_generation += 1 # 탐색 시작할 때 +1
        my_generation = self.search_generation
        self.target_class = target
        self.state = 'searching'
        self.miss_count = 0
        self.is_aligning = False

        start = time.monotonic()
        while time.monotonic() - start < SEARCH_TIMEOUT_SEC:
            if self.emergency_stop:
                self.state = 'idle'
                self.target_class = None
                self.search_generation += 1 # 종료 시 +1
                return 'fail'

            if goal_handle is not None and goal_handle.is_cancel_requested:
                self.state = 'idle'
                self.target_class = None
                self.search_generation += 1  # 종료 시 +1
                return 'fail'

            if self.state == 'arrived':
                self.target_class = None
                self.search_generation += 1  # 종료 시 +1
                return 'success'

            time.sleep(0.1)

        self.state = 'idle'
        self.target_class = None
        self.search_generation += 1  # 종료 시 +1
        return 'not_found'

    def do_move(self, direction: str, speed: str, time_s: int) -> bool:
        linear = LINEAR_SPEED.get(speed, LINEAR_SPEED['normal'])
        angular = ANGULAR_SPEED.get(speed, ANGULAR_SPEED['normal'])

        twist = Twist()
        if direction == 'forward':
            twist.linear.x = linear
        elif direction == 'backward':
            twist.linear.x = -linear
        elif direction == 'left':
            twist.linear.x = linear
            twist.angular.z = angular
        elif direction == 'right':
            twist.linear.x = linear
            twist.angular.z = -angular
        else:
            self.get_logger().error(f'알 수 없는 dir: {direction}')
            return False

        end = time.monotonic() + time_s
        while time.monotonic() < end:
            if self.emergency_stop:
                return False
            self.cmd_pub.publish(twist)
            time.sleep(0.1)

        return True

    def do_perform(self, action: str, speed: str, time_s: int) -> bool:
        linear = LINEAR_SPEED.get(speed, LINEAR_SPEED['normal'])
        angular = ANGULAR_SPEED.get(speed, ANGULAR_SPEED['normal'])

        if action == 'spin':
            return self._perform_spin(angular, time_s)
        elif action == 'circle':
            return self._perform_circle(linear, angular, time_s)
        elif action == 'bow':
            return self._perform_bow(linear, time_s)
        elif action == 'dance':
            return self._perform_dance(linear, angular, time_s)
        else:
            self.get_logger().error(f'알 수 없는 perform action: {action}')
            return False

    def _publish_for(self, twist: Twist, duration: float) -> bool:
        end = time.monotonic() + duration
        while time.monotonic() < end:
            if self.emergency_stop:
                return False
            self.cmd_pub.publish(twist)
            time.sleep(0.1)
        return True

    def _perform_spin(self, angular: float, time_s: int) -> bool:
        twist = Twist()
        twist.angular.z = angular
        return self._publish_for(twist, time_s)

    def _perform_circle(self, linear: float, angular: float, time_s: int) -> bool:
        twist = Twist()
        twist.linear.x = linear
        twist.angular.z = angular
        return self._publish_for(twist, time_s)

    def _perform_bow(self, linear: float, time_s: int) -> bool:
        half = max(time_s / 2.0, 0.5)

        forward = Twist()
        forward.linear.x = linear
        if not self._publish_for(forward, half):
            return False

        self.cmd_pub.publish(Twist())
        time.sleep(0.3)

        backward = Twist()
        backward.linear.x = -linear
        return self._publish_for(backward, half)

    def _perform_dance(self, linear: float, angular: float, time_s: int) -> bool:
        end = time.monotonic() + time_s
        step = 0.4
        going_left = True
        while time.monotonic() < end:
            twist = Twist()
            twist.angular.z = angular if going_left else -angular
            if not self._publish_for(twist, min(step, end - time.monotonic())):
                return False
            going_left = not going_left
        return True

    def do_stop(self, time_s: int) -> bool:
        end = time.monotonic() + time_s
        while time.monotonic() < end:
            if self.emergency_stop:
                return False
            time.sleep(0.1)
        return True

    def do_resume(self) -> bool:
        return not self.emergency_stop
    
    # 센서 콜백
    def image_callback(self, msg):
        if self.emergency_stop:
            self.cmd_pub.publish(Twist())
            return

        if self.target_class is None:
            return

        my_generation = self.search_generation

        frame = self.bridge.compressed_imgmsg_to_cv2(msg, desired_encoding='bgr8')
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE) # 본 시행에서는 카메라를 90도 돌려 설치함. 필요 시 수정
        orig_h, orig_w, _ = frame.shape
        small_frame = cv2.resize(frame, (orig_w // 2, orig_h // 2)) # 추론 속도를 위해 절반 크기로 resize
        h, w = small_frame.shape[:2]
        frame_center_x = w / 2

        results = self.model(small_frame, verbose=False)

        if self.search_generation != my_generation:
            return  # 추론하는 동안 이미 이 탐색이 끝났음 -> 결과 버림 (다음 action 시행)

        boxes = results[0].boxes
        target_box = None
        best_conf = 0

        for box in boxes:
            cls_id = int(box.cls[0])
            cls_name = self.model.names[cls_id]
            conf = float(box.conf[0])

            if cls_name == self.target_class and conf > best_conf: # 타겟과 이름이 일치하고 신뢰도가 제일 높은 box
                best_conf = conf
                target_box = box

        twist = Twist()

        # 타겟을 찾았을 때
        if target_box is not None: 
            self.miss_count = 0
            x1, y1, x2, y2 = target_box.xyxy[0].tolist()
            center_x = (x1 + x2) / 2
            box_height = y2 - y1
            height_ratio = box_height / h

            just_found = self.state not in ('approaching', 'arrived')

            if height_ratio > 0.4: # 충분히 가까우면 도착
                self.state = 'arrived'
                twist.linear.x = 0.0
                twist.angular.z = 0.0
                self.get_logger().info(f'도착! {self.target_class} 찾았습니다. 정지')
            elif just_found:
                # 회전 중 막 발견한 순간이면, 추론하는 동안 실제 각도는 더 돌아가 있었을 것
                # 일단 완전히 멈추고 다음 프레임(정지 상태에서 촬영)부터 정확히 보정
                self.state = 'approaching'
                twist.linear.x = 0.0
                twist.angular.z = 0.0
                self.get_logger().info('타겟 발견 - 정지 후 보정')
            else:
                self.state = 'approaching'
                error_x = center_x - frame_center_x

                enter_align = w * 0.25
                exit_align = w * 0.08

                if not self.is_aligning and abs(error_x) > enter_align:
                    self.is_aligning = True # 정렬 모드
                elif self.is_aligning and abs(error_x) < exit_align:
                    self.is_aligning = False # 접근 모드

                if self.is_aligning:
                    twist.linear.x = 0.0
                    twist.angular.z = -0.002 * error_x
                    self.get_logger().info(f'조준 중: error_x={error_x:.0f}')
                else:
                    speed = 0.1 * (1 - height_ratio / 0.4)
                    twist.linear.x = max(speed, 0.03)
                    twist.angular.z = -0.0008 * error_x
                    self.get_logger().info(
                        f'접근 중: error_x={error_x:.0f}, height_ratio={height_ratio:.2f}, speed={twist.linear.x:.3f}'
                    )
            self.cmd_pub.publish(twist)
        # 타겟을 놓쳤을 때
        else:
            self.miss_count += 1
            if self.state == 'approaching' and self.miss_count < self.miss_threshold:
                self.get_logger().info(f'일시적 미검출 ({self.miss_count}/{self.miss_threshold})')
            else:
                self.state = 'searching'
                twist.linear.x = 0.0
                twist.angular.z = 0.12
                self.get_logger().info('탐색 중... (제자리 회전)')
                self.cmd_pub.publish(twist)

def main(args=None):
    rclpy.init(args=args)
    node = FetchRobotNode()
    executor = MultiThreadedExecutor(num_threads=4) # 멀티 스레드
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        stop_twist = Twist()
        node.cmd_pub.publish(stop_twist)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()