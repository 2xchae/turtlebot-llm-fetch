from setuptools import find_packages, setup
import glob

package_name = 'turtlebot_llm_pc'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob.glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools', 'torch', 'transformers'],
    zip_safe=True,
    maintainer='채',
    maintainer_email='you@example.com',
    description='PC(GPU)에서 도는 model_server_node, command_parser_node, response_generator_node',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'model_server_node = turtlebot_llm_pc.model_server_node:main',
            'command_parser_node = turtlebot_llm_pc.command_parser_node:main',
            'response_generator_node = turtlebot_llm_pc.response_generator_node:main',
            'command_input_node = turtlebot_llm_pc.command_input_node:main',
            'response_display_node = turtlebot_llm_pc.response_display_node:main',
        ],
    },
)
