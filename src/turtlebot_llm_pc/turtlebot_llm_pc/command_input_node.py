"""
command_input_node

터미널에서 자연어 명령을 직접 입력받아 /user_command로 발행하는 사용자용 CLI
'stop' 입력 시 자연어 파싱 없이 바로 /emergency_stop을 발행 (비상정지)
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool

STOP_KEYWORDS = {'stop', '정지', '비상정지'}

class CommandInputNode(Node):
    def __init__(self):
        super().__init__('command_input_node')
        self.command_pub = self.create_publisher(String, 'user_command', 10) # user_command 발행
        self.emergency_pub = self.create_publisher(Bool, 'emergency_stop', 10) # emergency_stop 발행

    def run(self):
        print('명령을 입력하세요 (비상정지: stop, 종료: Ctrl+C)')
        while rclpy.ok():
            try:
                text = input('> ').strip()
            except EOFError:
                break

            if not text:
                continue

            if text.lower() in STOP_KEYWORDS:
                msg = Bool()
                msg.data = True
                self.emergency_pub.publish(msg)
                self.get_logger().warn('비상정지 발행')
                continue

            msg = String()
            msg.data = text
            self.command_pub.publish(msg)
            self.get_logger().info(f'명령 발행: "{text}"')


def main(args=None):
    rclpy.init(args=args)
    node = CommandInputNode()
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()