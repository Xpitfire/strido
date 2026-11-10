"""Strido in Gazebo Harmonic: model, ros2_control, sensor bridge and the gait node.

    ros2 launch strido_bringup gazebo.launch.py               # GUI
    ros2 launch strido_bringup gazebo.launch.py headless:=true

Topics (same contract as the robot, see docs/software.md): /cmd_vel in,
/joint_states, /imu/data, /scan, /camera/image_raw, /odom (gait dead reckoning),
/ground_truth/odom (simulator only) out.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, RegisterEventHandler
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

BRIDGED_TOPICS = [
    "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
    "/imu/data@sensor_msgs/msg/Imu[gz.msgs.IMU",
    "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
    "/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image",
    "/ground_truth/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
]


def generate_launch_description():
    bringup = FindPackageShare("strido_bringup")
    xacro_file = PathJoinSubstitution([FindPackageShare("strido_description"), "urdf", "strido.urdf.xacro"])
    world = LaunchConfiguration("world")
    description = ParameterValue(Command(["xacro ", xacro_file, " sim:=true"]), value_type=str)
    use_sim_time = {"use_sim_time": True}

    gz_gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([FindPackageShare("ros_gz_sim"), "/launch/gz_sim.launch.py"]),
        launch_arguments={"gz_args": ["-r ", world], "on_exit_shutdown": "true"}.items(),
        condition=UnlessCondition(LaunchConfiguration("headless")),
    )
    gz_headless = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([FindPackageShare("ros_gz_sim"), "/launch/gz_sim.launch.py"]),
        launch_arguments={"gz_args": ["-r -s --headless-rendering ", world], "on_exit_shutdown": "true"}.items(),
        condition=IfCondition(LaunchConfiguration("headless")),
    )
    spawn = Node(
        package="ros_gz_sim",
        executable="create",
        output="screen",
        arguments=["-name", "strido", "-topic", "robot_description", "-z", "0.28"],
    )
    joint_state_broadcaster = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_state_broadcaster", "--controller-manager-timeout", "60"],
    )
    leg_controller = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["leg_controller", "--controller-manager-timeout", "60"],
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument("world", default_value=PathJoinSubstitution([bringup, "worlds", "flat.sdf"])),
            DeclareLaunchArgument("headless", default_value="false"),
            DeclareLaunchArgument("use_policy", default_value="false"),
            DeclareLaunchArgument("policy", default_value=""),
            gz_gui,
            gz_headless,
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[{"robot_description": description}, use_sim_time],
            ),
            Node(package="ros_gz_bridge", executable="parameter_bridge", arguments=BRIDGED_TOPICS, output="screen"),
            spawn,
            RegisterEventHandler(OnProcessExit(target_action=spawn, on_exit=[joint_state_broadcaster])),
            RegisterEventHandler(OnProcessExit(target_action=joint_state_broadcaster, on_exit=[leg_controller])),
            Node(
                package="strido_control",
                executable="gait_node",
                output="screen",
                parameters=[use_sim_time],
                condition=UnlessCondition(LaunchConfiguration("use_policy")),
            ),
            Node(
                package="strido_control",
                executable="policy_node",
                output="screen",
                parameters=[{"policy": LaunchConfiguration("policy")}, use_sim_time],
                condition=IfCondition(LaunchConfiguration("use_policy")),
            ),
        ]
    )
