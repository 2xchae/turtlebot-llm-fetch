"""
response_display_node

/robot_response를 구독해서 응답 텍스트만 깔끔하게 출력하는 노드
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class ResponseDisplayNode(Node):
    def __init__(self):
        super().__init__('response_display_node')
        self.sub = self.create_subscription(String, 'robot_response', self.on_response, 10) # robot_response 구독
        print('로봇 응답 대기 중...\n')

    def on_response(self, msg: String):
        print(f'🤖 {msg.data}')


def main(args=None):
    rclpy.init(args=args)
    node = ResponseDisplayNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
