# Setup

## Requirements

전체 환경 정보는 [루트 README](../README.md#environment) 참고.

### PC

```bash
pip install torch transformers
```

### Raspberry Pi

```bash
sudo apt-get install ros-humble-v4l2-camera ros-humble-image-transport-plugins v4l-utils raspi-config
pip install ultralytics opencv-python
```
 
<sub> TurtleBot3 표준 패키지(`turtlebot3_bringup`)는 [공식 문서](https://emanual.robotis.com/docs/en/platform/turtlebot3/quick-start/)를 따라 미리 빌드되어 있어야 합니다.


## Build

```bash
git clone https://github.com/2xchae/turtlebot-llm-fetch.git
cd turtlebot-llm-fetch
colcon build
source install/setup.bash
```

PC와 Raspberry Pi는 각자 필요한 패키지만 선택 빌드해도 됩니다.

```bash
# PC
colcon build --packages-select turtlebot_llm_interfaces turtlebot_llm_pc
 
# Raspberry Pi
colcon build --packages-select turtlebot_llm_interfaces turtlebot_llm_robot
```

## Model checkpoint

[HuggingFace](https://huggingface.co/chaex2/turtlebot-llm-fetch-finetuned)에서
`ft_best.pt`를 다운로드합니다. 다운로드한 경로는 아래 [Run](#run) 단계에서
`checkpoint_path:=` 인자로 넘겨주면 되며, 소스 코드를 직접 수정할 필요는 없습니다.

## Run

### PC

`model_server_node`, `command_parser_node`, `response_generator_node`를 한 번에 실행합니다.

```bash
ros2 launch turtlebot_llm_pc pc_bringup.launch.py checkpoint_path:=/path/to/ft_best.pt
```

터미널 입출력용 노드는 별도로 실행합니다.

```bash
ros2 run turtlebot_llm_pc command_input_node
ros2 run turtlebot_llm_pc response_display_node
```

### Raspberry Pi

TurtleBot3 표준 노드(모터 구동)와 카메라 노드를 먼저 실행합니다.

```bash
ros2 launch turtlebot3_bringup robot.launch.py
ros2 run v4l2_camera v4l2_camera_node
```

다음으로 로봇 제어 노드를 실행합니다.

```bash
ros2 run turtlebot_llm_robot fetch_robot_node
```

## Network

PC와 Raspberry Pi가 서로의 토픽/서비스/액션을 주고받으려면 같은 네트워크에 연결되어 있고 같은 `ROS_DOMAIN_ID`를 사용해야 합니다.

```bash
export ROS_DOMAIN_ID=30   # 양쪽 다 같은 값으로 설정
```

## Example commands

`command_input_node` 실행 후 터미널에 자연어 명령을 입력하면 됩니다.

```
> 사과를 찾아서 왼쪽으로 돌아줘
search(apple) > move(dir=left, speed=normal)
```


비상정지는 `stop`, `정지`, `비상정지` 등을 입력하면 즉시 발동됩니다.