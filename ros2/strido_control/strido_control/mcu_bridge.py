"""Serial bridge between ROS 2 and the XIAO ESP32-S3 motion controller.

In:  /leg_controller/commands  std_msgs/Float64MultiArray  12 joint angles [rad], Go2 order
     /strido/estop            std_msgs/Bool               latched e-stop (true) / release (false)
     /strido/relax            std_msgs/Bool               true: servos limp (PCA9685 OE high)
     /strido/face             std_msgs/UInt8              LCD expression id
Out: /joint_states             sensor_msgs/JointState      joint angles the MCU applies (hobby servos have
                                                           no position feedback: commanded after clamping)
     /imu/data                 sensor_msgs/Imu             LSM6DSOX + Mahony filter, imu_link frame (axes aligned
                                                           with base_link); not published while the IMU is down
     /battery_state            sensor_msgs/BatteryState    INA260 on the logic branch (voltage = pack voltage,
                                                           current negative = discharging, REP/BatteryState convention)
     /diagnostics              diagnostic_msgs/DiagnosticArray  MCU status flags

Wire format: strido.protocol (COBS + CRC16), see docs/software.md ("Protocol").
No keep-alive: the controller's 200 ms command watchdog is fed only by joint commands, so a
dead gait/policy node makes the robot hold and then relax.
"""

import math

import rclpy
import serial
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import BatteryState, Imu, JointState
from std_msgs.msg import Bool, Float64MultiArray, UInt8

from strido import protocol
from strido.geometry import LEG_NAMES

JOINT_NAMES = [f"{leg}_{joint}_joint" for leg in LEG_NAMES for joint in ("hip", "thigh", "calf")]
FLAG_NAMES = {
    protocol.FLAG_ESTOP: "estop",
    protocol.FLAG_RELAXED: "relaxed",
    protocol.FLAG_WATCHDOG: "watchdog",
    protocol.FLAG_IMU_OK: "imu_ok",
    protocol.FLAG_POWER_OK: "power_ok",
    protocol.FLAG_PWM_OK: "pwm_ok",
    protocol.FLAG_CLAMPED: "clamped",
    protocol.FLAG_CALIBRATION_MODE: "calibration_mode",
}
READ_CHUNK_BYTES = 4096


class McuBridge(Node):
    def __init__(self):
        super().__init__("mcu_bridge")
        port = self.declare_parameter("port", "/dev/strido_mcu").value
        self.serial = serial.Serial(port, 115200, timeout=0)  # USB CDC ignores the baud rate
        self.reader = protocol.FrameReader()
        self.seq = 0
        self.relaxed = False
        self.last_q = None
        self.joint_states = self.create_publisher(JointState, "/joint_states", 10)
        self.imu = self.create_publisher(Imu, "/imu/data", 10)
        self.battery = self.create_publisher(BatteryState, "/battery_state", 10)
        self.diagnostics = self.create_publisher(DiagnosticArray, "/diagnostics", 10)
        self.create_subscription(Float64MultiArray, "/leg_controller/commands", self.on_command, 10)
        self.create_subscription(Bool, "/strido/estop", self.on_estop, 10)
        self.create_subscription(Bool, "/strido/relax", self.on_relax, 10)
        self.create_subscription(UInt8, "/strido/face", self.on_face, 10)
        self.create_timer(0.002, self.poll)
        self.get_logger().info(f"MCU bridge on {port}")

    def next_seq(self) -> int:
        self.seq = (self.seq + 1) & 0xFFFF
        return self.seq

    def on_command(self, msg: Float64MultiArray) -> None:
        if len(msg.data) != 12 or not all(math.isfinite(v) for v in msg.data):
            self.get_logger().warn(f"ignoring command: expected 12 finite values, got {list(msg.data)}")
            return
        self.last_q = list(msg.data)
        mode = protocol.MODE_RELAX if self.relaxed else protocol.MODE_POSITION
        self.serial.write(protocol.joint_command(self.next_seq(), mode, self.last_q))

    def on_estop(self, msg: Bool) -> None:
        self.serial.write(protocol.estop(msg.data))
        self.get_logger().warn(f"e-stop {'ENGAGED' if msg.data else 'released'}")

    def on_relax(self, msg: Bool) -> None:
        self.relaxed = msg.data
        q = self.last_q if self.last_q is not None else [0.0] * 12  # relax works before the first command too
        mode = protocol.MODE_RELAX if self.relaxed else protocol.MODE_POSITION
        if mode == protocol.MODE_RELAX or self.last_q is not None:
            self.serial.write(protocol.joint_command(self.next_seq(), mode, q))
        self.get_logger().info(f"servos {'relaxed' if self.relaxed else 'enabled'}")

    def on_face(self, msg: UInt8) -> None:
        self.serial.write(protocol.display(msg.data))

    def poll(self) -> None:
        data = self.serial.read(READ_CHUNK_BYTES)
        if not data:
            return
        for message_type, payload in self.reader.feed(data):
            if message_type == protocol.STATE and len(payload) == protocol.STATE_PAYLOAD_SIZE:
                self.publish_state(protocol.State.unpack(payload))
            elif message_type == protocol.LOG:
                self.get_logger().info(f"mcu: {payload.decode('ascii', 'replace')}")

    def publish_state(self, state: protocol.State) -> None:
        stamp = self.get_clock().now().to_msg()
        joints = JointState(name=JOINT_NAMES, position=[float(v) for v in state.q])
        joints.header.stamp = stamp
        self.joint_states.publish(joints)
        if state.status & protocol.FLAG_IMU_OK:  # never publish a fake upright orientation
            imu = Imu()
            imu.header.stamp = stamp
            imu.header.frame_id = "imu_link"
            imu.orientation.w, imu.orientation.x, imu.orientation.y, imu.orientation.z = map(float, state.quat_wxyz)
            imu.angular_velocity.x, imu.angular_velocity.y, imu.angular_velocity.z = map(float, state.gyro)
            imu.linear_acceleration.x, imu.linear_acceleration.y, imu.linear_acceleration.z = map(float, state.accel)
            self.imu.publish(imu)
        battery = BatteryState(
            voltage=float(state.bus_voltage),
            current=-float(state.current),
            present=True,
            power_supply_technology=BatteryState.POWER_SUPPLY_TECHNOLOGY_LIPO,
        )
        battery.header.stamp = stamp
        self.battery.publish(battery)
        status = DiagnosticStatus(name="strido/mcu", hardware_id="xiao_esp32s3")
        status.values = [KeyValue(key=name, value=str(bool(state.status & bit))) for bit, name in FLAG_NAMES.items()]
        healthy = (state.status & protocol.FLAG_PWM_OK) and not (
            state.status & (protocol.FLAG_ESTOP | protocol.FLAG_WATCHDOG)
        )
        status.level = DiagnosticStatus.OK if healthy else DiagnosticStatus.WARN
        status.message = "ok" if healthy else "check flags"
        diagnostics = DiagnosticArray(status=[status])
        diagnostics.header.stamp = stamp
        self.diagnostics.publish(diagnostics)


def main():
    rclpy.init()
    node = McuBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
