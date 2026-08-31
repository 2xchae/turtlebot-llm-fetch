"""
response_generator_node

/robot_command (RobotCommand) 구독 -> fetch_robot_node의 ExecuteSequence 액션에 goal 전송 (액션 클라이언트) 
-> feedback(액션 1개 끝날 때)마다 model_server에 "상태: ... 답변: " 프롬프트로 서비스 호출 
-> /robot_response (std_msgs/String)로 즉시 발행
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String

from turtlebot_llm_interfaces.msg import RobotCommand
from turtlebot_llm_interfaces.srv import GenerateText
from turtlebot_llm_interfaces.action import ExecuteSequence # ExecuteSequence
from turtlebot_llm_pc.status_formatter import status_to_string


class ResponseGeneratorNode(Node):
    def __init__(self):
        super().__init__('response_generator_node')

        self.gen_client = self.create_client(GenerateText, 'generate_text') # 서비스 클라이언트 
        while not self.gen_client.wait_for_service(timeout_sec=2.0):
            self.get_logger().info('model_server의 generate_text 서비스 대기 중...')

        self.action_client = ActionClient(self, ExecuteSequence, 'execute_sequence') # 액션 클라이언트

        self.sub = self.create_subscription(RobotCommand, 'robot_command', self.on_robot_command, 10) # robot_command 구독
        self.pub = self.create_publisher(String, 'robot_response', 10) # robot_response 발행

        self.get_logger().info('response_generator_node 준비 완료.')

    def on_robot_command(self, msg: RobotCommand): # goal 전송
        if not self.action_client.wait_for_server(timeout_sec=2.0):
            self.get_logger().error('fetch_robot_node의 execute_sequence 액션 서버를 찾을 수 없음.')
            return

        goal = ExecuteSequence.Goal()
        goal.command = msg

        self.get_logger().info(f'{len(msg.actions)}개 액션 시퀀스 goal 전송.')
        send_goal_future = self.action_client.send_goal_async(goal, feedback_callback=self.on_feedback)
        send_goal_future.add_done_callback(self.on_goal_response)

    def on_goal_response(self, future): # goal이 수락됐는지 확인 후 result 기다리기
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('goal이 거부됨.')
            return
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.on_result)

    def on_result(self, future): # 시퀀스 전체 끝난 뒤 요약. 발행x, 로그로만 사용
        result = future.result().result
        self.get_logger().info(
            f'시퀀스 종료. 성공 {result.success_count} / 실패 {result.fail_count}'
        )

    def on_feedback(self, feedback_msg): # 액션 하나 끝날 때마다
        fb = feedback_msg.feedback
        status = fb.status

        try:
            status_str = status_to_string(status) # msg -> string
        except ValueError as e:
            self.get_logger().error(str(e))
            return

        req = GenerateText.Request()
        req.prompt = f'상태: {status_str} 답변: '
        req.do_sample = False  # 필요하면 True + temperature로 바꿔서 다양성 줄 수 있음

        future = self.gen_client.call_async(req)
        future.add_done_callback(
            lambda f: self.on_response_generated(f, fb.current_index, fb.total_count)
        )

    def on_response_generated(self, future, current_index, total_count): # 최종 발행
        try:
            response_text = future.result().generated_text
        except Exception as e:
            self.get_logger().error(f'응답 생성 실패: {e}')
            return

        self.get_logger().info(f'[{current_index + 1}/{total_count}] {response_text}')

        out = String()
        out.data = response_text
        self.pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = ResponseGeneratorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
