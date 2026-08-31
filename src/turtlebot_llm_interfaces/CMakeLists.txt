cmake_minimum_required(VERSION 3.8)
project(turtlebot_llm_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(action_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Action.msg"
  "msg/RobotCommand.msg"
  "msg/RobotStatus.msg"
  "srv/GenerateText.srv"
  "action/ExecuteSequence.action"
  DEPENDENCIES action_msgs
)

ament_package()
