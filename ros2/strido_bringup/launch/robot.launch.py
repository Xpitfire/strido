"""Strido on the robot (Raspberry Pi 5): MCU bridge, gait, model, LiDAR and camera.

    ros2 launch strido_bringup robot.launch.py
    ros2 launch strido_bringup robot.launch.py lidar:=false
    ros2 launch strido_bringup robot.launch.py camera:=true   # with camera_ros installed (docs/software.md)

Start-up: insert the arming loop key with the robot lying in its rest pose *before*
launching; the gait node then commands the rest pose and stands up within 3 s.
/strido/estop (std_msgs/Bool) disables the servo outputs at any time.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    xacro_file = PathJoinSubstitution([FindPackageShare("strido_description"), "urdf", "strido.urdf.xacro"])
    description = ParameterValue(Command(["xacro ", xacro_file]), value_type=str)
    lidar = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([FindPackageShare("sllidar_ros2"), "/launch/sllidar_c1_launch.py"]),
        launch_arguments={"serial_port": LaunchConfiguration("lidar_port"), "frame_id": "lidar_link"}.items(),
        condition=IfCondition(LaunchConfiguration("lidar")),
    )
    camera = Node(
        package="camera_ros",
        executable="camera_node",
        name="camera",
        parameters=[{"width": 1280, "height": 720, "frame_id": "camera_optical_frame"}],
        remappings=[("~/image_raw", "/camera/image_raw"), ("~/camera_info", "/camera/camera_info")],
        condition=IfCondition(LaunchConfiguration("camera")),
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument("mcu_port", default_value="/dev/strido_mcu"),
            DeclareLaunchArgument("lidar_port", default_value="/dev/rplidar"),
            DeclareLaunchArgument("lidar", default_value="true"),
            DeclareLaunchArgument("camera", default_value="false"),  # needs camera_ros + RPi libcamera fork on the host
            DeclareLaunchArgument("use_policy", default_value="false"),
            DeclareLaunchArgument("policy", default_value=""),
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[{"robot_description": description}],
            ),
            Node(
                package="strido_control",
                executable="mcu_bridge",
                output="screen",
                parameters=[{"port": LaunchConfiguration("mcu_port")}],
            ),
            Node(
                package="strido_control",
                executable="gait_node",
                output="screen",
                parameters=[],
                condition=UnlessCondition(LaunchConfiguration("use_policy")),
            ),
            Node(
                package="strido_control",
                executable="policy_node",
                output="screen",
                parameters=[{"policy": LaunchConfiguration("policy")}],
                condition=IfCondition(LaunchConfiguration("use_policy")),
            ),
            lidar,
            camera,
        ]
    )
