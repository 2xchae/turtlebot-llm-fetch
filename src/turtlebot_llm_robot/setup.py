from setuptools import find_packages, setup

package_name = 'turtlebot_llm_robot'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'ultralytics', 'opencv-python'],
    zip_safe=True,
    maintainer='채',
    maintainer_email='you@example.com',
    description='라즈베리파이에서 도는 fetch_robot_node (모터 제어 + YOLO 연동)',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'fetch_robot_node = turtlebot_llm_robot.fetch_robot_node:main',
        ],
    },
)
