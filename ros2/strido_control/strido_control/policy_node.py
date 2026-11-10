"""Learned-policy node: /cmd_vel + /imu/data -> /leg_controller/commands at 50 Hz.

Drop-in alternative to gait_node for policies trained with strido_sim.rl.train
(exported policy.npz). Observation layout and action mapping: strido.policy.

    ros2 run strido_control policy_node --ros-args -p policy:=/path/to/policy.npz
"""

import math

import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Float64MultiArray

from strido.gait import REST_HEIGHT_M, clamp_leg, stand_pose
from strido.geometry import LEG_NAMES
from strido.policy import ACTION_SCALE, CONTROL_DT, GAIT_PERIOD_S, MlpPolicy, clip_command, slew_limit


def gravity_in_base(x: float, y: float, z: float, w: float) -> np.ndarray:
    """R(q)^T @ (0, 0, -1): third row of R, negated."""
    return -np.array([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)])


class PolicyNode(Node):
    def __init__(self):
        super().__init__("policy_node")
        path = self.declare_parameter("policy", "").value
        assert path, "set the 'policy' parameter to an exported policy.npz"
        self.stand_up_s = self.declare_parameter("stand_up_s", 3.0).value
        self.cmd_timeout_s = self.declare_parameter("cmd_timeout_s", 0.5).value
        self.policy = MlpPolicy.load(path)
        self.default_q = stand_pose()
        self.rest_q = stand_pose(REST_HEIGHT_M)
        self.command = np.zeros(3)
        self.last_cmd_time = None
        self.gyro = np.zeros(3)
        self.gravity = np.array([0.0, 0.0, -1.0])
        self.imu_seen = False
        self.last_action = np.zeros(12)
        self.start_time = None
        self.policy_steps = 0
        self.commands = self.create_publisher(Float64MultiArray, "/leg_controller/commands", 10)
        self.create_subscription(Twist, "/cmd_vel", self.on_cmd_vel, 10)
        self.create_subscription(Imu, "/imu/data", self.on_imu, 50)
        self.targets = self.default_q.copy()
        self.create_timer(CONTROL_DT, self.tick)
        self.get_logger().info(f"policy {path}")

    def on_cmd_vel(self, msg: Twist) -> None:
        self.command = np.array([msg.linear.x, msg.linear.y, msg.angular.z])
        self.last_cmd_time = self.get_clock().now()

    def on_imu(self, msg: Imu) -> None:
        q = msg.orientation
        self.gravity = gravity_in_base(q.x, q.y, q.z, q.w)
        self.gyro = np.array([msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z])
        self.imu_seen = True

    def publish(self, q) -> None:
        self.commands.publish(Float64MultiArray(data=[float(v) for v in q]))

    def tick(self) -> None:
        now = self.get_clock().now()
        if now.nanoseconds == 0 or not self.imu_seen:
            return
        if self.start_time is None:
            self.start_time = now
        elapsed = (now - self.start_time).nanoseconds * 1e-9
        if elapsed < self.stand_up_s:
            blend = 0.5 - 0.5 * math.cos(math.pi * elapsed / self.stand_up_s)
            self.publish((1.0 - blend) * self.rest_q + blend * self.default_q)
            return
        stale = self.last_cmd_time is None or (now - self.last_cmd_time).nanoseconds * 1e-9 > self.cmd_timeout_s
        command = np.zeros(3) if stale else clip_command(self.command)  # stay inside the trained range
        phase = 2 * math.pi * self.policy_steps * CONTROL_DT / GAIT_PERIOD_S
        observation = np.concatenate(
            [self.gyro, self.gravity, command, self.last_action, [math.sin(phase), math.cos(phase)]]
        )
        action = self.policy(observation)
        self.last_action = action
        self.policy_steps += 1
        # same order as training and firmware: slew limit, then joint and knee-crank clamp
        limited = slew_limit(self.default_q + ACTION_SCALE * action, self.targets).reshape(4, 3)
        self.targets = np.concatenate([clamp_leg(name, tuple(leg)) for name, leg in zip(LEG_NAMES, limited)])
        self.publish(self.targets)


def main():
    rclpy.init()
    node = PolicyNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
