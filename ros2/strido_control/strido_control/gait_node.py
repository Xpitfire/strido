"""Gait node: /cmd_vel -> 12 joint targets on /leg_controller/commands (Go2 order).

Startup: rest pose (legs folded, body just above the ground) ramps to the stand
pose over `stand_up_s`. Without /cmd_vel for `cmd_timeout_s` the robot stands
still. /odom + TF odom->base_link integrate the *commanded* body velocity
(dead reckoning, no slip model): good enough for teleoperation and a seed for
SLAM; use a LiDAR odometry/SLAM source for navigation.
"""

import math

import numpy as np
import rclpy
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from tf2_ros import TransformBroadcaster

from strido.gait import REST_HEIGHT_M, GaitConfig, TrotGait, stand_pose


class GaitNode(Node):
    def __init__(self):
        super().__init__("gait_node")
        self.rate_hz = self.declare_parameter("rate_hz", 100.0).value
        self.body_height = self.declare_parameter("body_height", 0.17).value
        self.stand_up_s = self.declare_parameter("stand_up_s", 3.0).value
        self.cmd_timeout_s = self.declare_parameter("cmd_timeout_s", 0.5).value
        self.accel_limit = self.declare_parameter("accel_limit", 0.5).value  # m/s^2 and rad/s^2
        self.publish_tf = self.declare_parameter("publish_tf", True).value
        assert self.rate_hz > 0 and self.stand_up_s > 0
        self.gait = TrotGait(GaitConfig(body_height=self.body_height))
        self.rest = stand_pose(REST_HEIGHT_M)
        self.stand = stand_pose(self.body_height)
        self.target = np.zeros(3)
        self.velocity = np.zeros(3)
        self.last_cmd_time = None
        self.start_time = None
        self.pose = np.zeros(3)  # x, y, yaw in odom
        self.commands = self.create_publisher(Float64MultiArray, "/leg_controller/commands", 10)
        self.odom = self.create_publisher(Odometry, "/odom", 10)
        self.tf = TransformBroadcaster(self) if self.publish_tf else None
        self.create_subscription(Twist, "/cmd_vel", self.on_cmd_vel, 10)
        self.timer = self.create_timer(1.0 / self.rate_hz, self.tick)

    def on_cmd_vel(self, msg: Twist) -> None:
        self.target = np.array([msg.linear.x, msg.linear.y, msg.angular.z])
        self.last_cmd_time = self.get_clock().now()

    def tick(self) -> None:
        now = self.get_clock().now()
        if now.nanoseconds == 0:  # simulated clock not running yet
            return
        if self.start_time is None:
            self.start_time = now
        dt = 1.0 / self.rate_hz
        elapsed = (now - self.start_time).nanoseconds * 1e-9
        if elapsed < self.stand_up_s:
            blend = 0.5 - 0.5 * math.cos(math.pi * elapsed / self.stand_up_s)  # smooth 0 -> 1
            self.publish((1.0 - blend) * self.rest + blend * self.stand)
            return
        stale = self.last_cmd_time is None or (now - self.last_cmd_time).nanoseconds * 1e-9 > self.cmd_timeout_s
        target = np.zeros(3) if stale else self.target
        step = self.accel_limit * dt
        self.velocity += np.clip(target - self.velocity, -step, step)
        self.gait.set_command(*self.velocity)
        self.velocity = self.gait.command.copy()  # keep the integrator within the gait limits
        self.publish(self.gait.step(dt))
        self.integrate(dt, now)

    def publish(self, q) -> None:
        self.commands.publish(Float64MultiArray(data=[float(v) for v in q]))

    def integrate(self, dt: float, now) -> None:
        vx, vy, wz = self.velocity
        yaw = self.pose[2]
        self.pose += np.array(
            [(vx * math.cos(yaw) - vy * math.sin(yaw)) * dt, (vx * math.sin(yaw) + vy * math.cos(yaw)) * dt, wz * dt]
        )
        msg = Odometry()
        msg.header.stamp = now.to_msg()
        msg.header.frame_id = "odom"
        msg.child_frame_id = "base_link"
        msg.pose.pose.position.x, msg.pose.pose.position.y = float(self.pose[0]), float(self.pose[1])
        msg.pose.pose.position.z = float(self.body_height)
        msg.pose.pose.orientation.z = math.sin(self.pose[2] / 2)
        msg.pose.pose.orientation.w = math.cos(self.pose[2] / 2)
        msg.twist.twist.linear.x, msg.twist.twist.linear.y, msg.twist.twist.angular.z = float(vx), float(vy), float(wz)
        self.odom.publish(msg)
        if self.tf is not None:
            transform = TransformStamped()
            transform.header = msg.header
            transform.child_frame_id = "base_link"
            transform.transform.translation.x = msg.pose.pose.position.x
            transform.transform.translation.y = msg.pose.pose.position.y
            transform.transform.translation.z = msg.pose.pose.position.z
            transform.transform.rotation = msg.pose.pose.orientation
            self.tf.sendTransform(transform)


def main():
    rclpy.init()
    node = GaitNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
