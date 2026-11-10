"""Gazebo smoke test: stand up, walk forward on /cmd_vel, check the simulator ground truth.

Pass criteria (exit code 0): all sensor topics alive, base still upright
(|roll|, |pitch| < 0.5 rad, height > 0.10 m) and >= `min_forward_m` forward
progress after `walk_s` seconds at `vx` m/s. Prints one JSON summary line.
"""

import json
import math
import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import Image, Imu, JointState, LaserScan


def roll_pitch(q) -> tuple:
    roll = math.atan2(2 * (q.w * q.x + q.y * q.z), 1 - 2 * (q.x * q.x + q.y * q.y))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (q.w * q.y - q.z * q.x))))
    return roll, pitch


class WalkSmoke(Node):
    def __init__(self):
        super().__init__("walk_smoke")
        self.settle_s = self.declare_parameter("settle_s", 6.0).value
        self.walk_s = self.declare_parameter("walk_s", 8.0).value
        self.vx = self.declare_parameter("vx", 0.15).value
        self.min_forward_m = self.declare_parameter("min_forward_m", 0.4).value
        self.timeout_s = self.declare_parameter("timeout_s", 120.0).value
        self.seen = {"joint_states": 0, "imu": 0, "scan": 0, "camera": 0, "odom": 0}
        self.odom = None
        self.scan_min = math.inf
        self.start_pose = None
        self.start_time = None
        self.walk_start = None
        self.result = None
        self.cmd = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(JointState, "/joint_states", lambda m: self.count("joint_states"), 10)
        self.create_subscription(Imu, "/imu/data", lambda m: self.count("imu"), 10)
        self.create_subscription(LaserScan, "/scan", self.on_scan, 10)
        self.create_subscription(Image, "/camera/image_raw", lambda m: self.count("camera"), 10)
        self.create_subscription(Odometry, "/ground_truth/odom", self.on_odom, 10)
        self.create_timer(0.05, self.tick)

    def count(self, key: str) -> None:
        self.seen[key] += 1

    def on_scan(self, msg: LaserScan) -> None:
        self.count("scan")
        finite = [r for r in msg.ranges if math.isfinite(r) and r > msg.range_min]
        if finite:
            self.scan_min = min(self.scan_min, min(finite))

    def on_odom(self, msg: Odometry) -> None:
        self.count("odom")
        self.odom = msg

    def now_s(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def tick(self) -> None:
        now = self.now_s()
        if now == 0.0 or self.odom is None:
            return
        if self.start_time is None:
            self.start_time = now
        elapsed = now - self.start_time
        if elapsed > self.timeout_s:
            self.finish(False, "timeout")
            return
        if elapsed < self.settle_s:
            return
        pose = self.odom.pose.pose
        if self.walk_start is None:
            self.walk_start = now
            self.start_pose = (pose.position.x, pose.position.y)
        if now - self.walk_start < self.walk_s:
            msg = Twist()
            msg.linear.x = float(self.vx)
            self.cmd.publish(msg)
            return
        self.cmd.publish(Twist())
        roll, pitch = roll_pitch(pose.orientation)
        forward = pose.position.x - self.start_pose[0]
        upright = abs(roll) < 0.5 and abs(pitch) < 0.5 and pose.position.z > 0.10
        alive = all(self.seen[key] > 0 for key in self.seen)
        ok = upright and alive and forward >= self.min_forward_m
        self.finish(
            ok,
            "ok" if ok else "criteria failed",
            forward=forward,
            lateral=pose.position.y - self.start_pose[1],
            height=pose.position.z,
            roll=roll,
            pitch=pitch,
        )

    def finish(self, ok: bool, reason: str, **values) -> None:
        if self.result is not None:
            return
        summary = {"ok": ok, "reason": reason, "messages": self.seen, "scan_min_m": self.scan_min}
        summary.update({key: round(value, 4) for key, value in values.items()})
        print(json.dumps(summary), flush=True)
        self.result = ok


def main():
    rclpy.init()
    node = WalkSmoke()
    deadline = time.monotonic() + node.timeout_s  # wall clock: also covers "simulation never started"
    while rclpy.ok() and node.result is None:
        rclpy.spin_once(node, timeout_sec=0.1)
        if time.monotonic() > deadline:
            node.finish(False, "timeout (wall clock)")
    ok = bool(node.result)
    node.destroy_node()
    rclpy.try_shutdown()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
