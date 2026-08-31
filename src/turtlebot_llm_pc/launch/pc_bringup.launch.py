# model_server_node, command_parser_node, response_generator_node를 한번에 실행
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    checkpoint_path_arg = DeclareLaunchArgument(
        'checkpoint_path',
        default_value='/path/to/ft_best.pt',
        description='파인튜닝 체크포인트(.pt) 경로',
    )
    max_new_tokens_arg = DeclareLaunchArgument(
        'max_new_tokens',
        default_value='200',
        description='한 번에 생성할 최대 토큰 수',
    )

    model_server_node = Node(
        package='turtlebot_llm_pc',
        executable='model_server_node',
        name='model_server_node',
        output='screen',
        parameters=[{
            'checkpoint_path': LaunchConfiguration('checkpoint_path'),
            'max_new_tokens': LaunchConfiguration('max_new_tokens'),
        }],
    )

    command_parser_node = Node(
        package='turtlebot_llm_pc',
        executable='command_parser_node',
        name='command_parser_node',
        output='screen',
    )

    response_generator_node = Node(
        package='turtlebot_llm_pc',
        executable='response_generator_node',
        name='response_generator_node',
        output='screen',
    )

    return LaunchDescription([
        checkpoint_path_arg,
        max_new_tokens_arg,
        model_server_node,
        command_parser_node,
        response_generator_node,
    ])