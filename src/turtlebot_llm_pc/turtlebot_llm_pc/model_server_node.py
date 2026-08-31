"""
model_server_node

PC(GPU)에서 ft_best.pt를 1번 로딩하고 GenerateText 서비스로 노출
command_parser_node와 response_generator_node가 이 서비스를 호출
같은 모델 가중치를 공유하며 각자의 프롬프트("명령: ...", "상태: ...")를 생성
"""

import torch
import rclpy
from rclpy.node import Node

from turtlebot_llm_interfaces.srv import GenerateText
from turtlebot_llm_pc.model_utils import load_tokenizer, load_model, generate


CHECKPOINT_PATH = "/path/to/ft_best.pt"


class ModelServerNode(Node):
    def __init__(self):
        super().__init__('model_server_node')

        self.declare_parameter('checkpoint_path', CHECKPOINT_PATH)
        self.declare_parameter('max_new_tokens', 200)

        checkpoint_path = self.get_parameter('checkpoint_path').get_parameter_value().string_value
        self.max_new_tokens = self.get_parameter('max_new_tokens').get_parameter_value().integer_value

        # 모델 로드
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.get_logger().info(f'device={self.device}, checkpoint={checkpoint_path} 로딩 중...')

        self.tokenizer = load_tokenizer()
        self.model = load_model(checkpoint_path, self.tokenizer, self.device)

        self.get_logger().info('모델 로딩 완료. GenerateText 서비스 준비.')

        # 서비스 등록
        self.srv = self.create_service(GenerateText, 'generate_text', self.handle_generate)

    def handle_generate(self, request, response): # 요청 처리
        try:
            text = generate(
                self.model,
                self.tokenizer,
                request.prompt,
                self.device,
                max_new_tokens=self.max_new_tokens,
                do_sample=request.do_sample,
                temperature=request.temperature if request.temperature > 0 else 1.0,
            )
            response.generated_text = text
        except Exception as e:
            self.get_logger().error(f'생성 실패: {e}')
            response.generated_text = ''
        return response


def main(args=None):
    rclpy.init(args=args)
    node = ModelServerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
