"""
command_parser_node

/user_command (std_msgs/String) 구독 -> model_server의 GenerateText 서비스 호출 ("명령: {text} 답변: " 프롬프트, greedy) 
-> 액션 문자열 파싱 -> /robot_command 발행
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from turtlebot_llm_interfaces.msg import RobotCommand, Action # msg
from turtlebot_llm_interfaces.srv import GenerateText # srv
from turtlebot_llm_pc.action_parser import parse_action_string # 파서

# RobotCommand.actions에 넣기 위해 파서에서 얻은 dict를 msg로 변환
def action_dict_to_msg(d: dict) -> Action: 
    msg = Action()
    msg.type = d['type']
    msg.target = d['target']
    msg.dir = d['dir']
    msg.speed = d['speed']
    msg.action = d['action']
    msg.time = d['time']
    msg.repeat = d['repeat']
    return msg


class CommandParserNode(Node):
    def __init__(self):
        super().__init__('command_parser_node')

        self.client = self.create_client(GenerateText, 'generate_text')
        while not self.client.wait_for_service(timeout_sec=2.0):
            self.get_logger().info('model_server의 generate_text 서비스 대기 중...')

        self.sub = self.create_subscription(String, 'user_command', self.on_user_command, 10) # user_command 구독
        self.pub = self.create_publisher(RobotCommand, 'robot_command', 10) # robot_command 발행

        self.get_logger().info('command_parser_node 준비 완료.')

    def on_user_command(self, msg: String): # user_command에 msg 도착 시 호출되는 콜백
        text = msg.data.strip()
        if not text:
            return

        req = GenerateText.Request()
        req.prompt = f'명령: {text} 답변: '
        req.do_sample = False  # exact-match 학습된 태스크라 greedy 고정

        future = self.client.call_async(req) # 비동기
        future.add_done_callback(lambda f: self.on_parsed(f, text))

    def on_parsed(self, future, original_text): 
        try:
            action_string = future.result().generated_text
        except Exception as e:
            self.get_logger().error(f'model_server 호출 실패: {e}')
            return

        self.get_logger().info(f'"{original_text}" -> "{action_string}"')

        try:
            action_dicts = parse_action_string(action_string) # 파싱
        except ValueError as e:
            self.get_logger().error(f'액션 문자열 파싱 실패: {e}')
            return

        if not action_dicts:
            self.get_logger().warn('파싱 결과가 비어있음. 발행 생략.')
            return

        cmd_msg = RobotCommand()
        cmd_msg.actions = [action_dict_to_msg(d) for d in action_dicts] # 배열에 채우기
        self.pub.publish(cmd_msg) # 최종 발행


def main(args=None):
    rclpy.init(args=args)
    node = CommandParserNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
