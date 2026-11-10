# Learn

The Learn wiki explains the engineering behind Strido. You don't need it to build the robot, but it covers why the robot is built this way. Every article starts from the real robot: the servos, rails and parts you hold, the firmware and ROS 2 code in this repository, and the numbers the verification gates check. Each one ends with a few self-check questions and links to the primary sources.

## Learning paths

| If you want to… | Read in this order |
|---|---|
| Build the robot with confidence | [3D printing](making/3d-printing.md) → [Fasteners](making/fasteners.md) → [Tools and workshop](making/tools-and-workshop.md) → [Cable management](making/cable-management.md) → [Safety](making/safety.md) |
| Understand the electronics | [Power electronics](hardware/power.md) → [LiPo batteries](hardware/batteries.md) → [Servos](hardware/servos.md) → [Buses](hardware/buses.md) → [Sensors](hardware/sensors.md) |
| Get the computers running | [Microcontrollers and the Pi](hardware/microcontrollers.md) → [Linux on the Pi](software/linux-on-the-pi.md) → [Docker](software/docker.md) → [Firmware](software/firmware.md) → [ROS 2](software/ros2.md) |
| Know what can break | [Strength, torque and failure](making/strength.md) → [Fasteners](making/fasteners.md) → [Mechanics and bearings](hardware/mechanics.md) |
| Make it walk better | [Mechanics and bearings](hardware/mechanics.md) → [Kinematics and gaits](software/kinematics-and-gaits.md) → [Simulation and RL](software/simulation-and-rl.md) |
| Learn robotics from the ground up | [Frames and rotations](theory/frames-and-rotations.md) → [Kinematics](theory/kinematics.md) → [Statics and dynamics](theory/statics-and-dynamics.md) → [Control](theory/control.md) → [Legged locomotion](theory/legged-locomotion.md) → [State estimation](theory/state-estimation.md) → [Reinforcement learning](theory/reinforcement-learning.md) |
| Change the design | [CAD as code](software/cad-as-code.md) → [Mechanics and bearings](hardware/mechanics.md) → [3D printing](making/3d-printing.md) |

## Robotics theory

The mathematics behind a walking robot, each worked on Strido's own leg, servos and sensors.

- [Frames and rotations](theory/frames-and-rotations.md): coordinate frames, rotation matrices, quaternions, homogeneous transforms and the robot's tf tree.
- [Kinematics](theory/kinematics.md): forward and inverse kinematics of the leg, the knee four-bar, the Jacobian and singularities.
- [Statics and dynamics](theory/statics-and-dynamics.md): virtual work, $\boldsymbol{\tau} = \mathbf{J}^\top \mathbf{F}$, mechanical advantage, inertia and the torque and power a joint needs.
- [Control](theory/control.md): feedback, PD and PID control, sampling rates and the servo's own position loop.
- [Legged locomotion](theory/legged-locomotion.md): gaits, support polygons, stability and how the trot generator places the feet.
- [State estimation](theory/state-estimation.md): IMU models, complementary and Mahony filters, the Kalman filter and odometry.
- [Reinforcement learning](theory/reinforcement-learning.md): Markov decision processes, policy gradients, PPO and sim-to-real.

## Hardware

- [Servos](hardware/servos.md): pulse widths, torque, stall current, and centring the 12 SPT5435LV joints.
- [LiPo batteries](hardware/batteries.md): the 2S pack, its voltage window, charging, storage and handling.
- [Power electronics](hardware/power.md): from XT60 to fuses, UBECs and the regulator, wire gauges and power monitoring.
- [Microcontrollers and the Pi](hardware/microcontrollers.md): why a real-time ESP32-S3 sits next to a Linux Raspberry Pi 5.
- [Buses: I²C, UART, SPI, PWM](hardware/buses.md): how the boards talk to each other.
- [Sensors](hardware/sensors.md): IMU, LiDAR, camera and power monitor, and what the software does with them.
- [Mechanics and bearings](hardware/mechanics.md): the leg linkage, bearings, fits and joint limits.

## Software

- [Linux on the Pi](software/linux-on-the-pi.md): the operating system, headless setup, SSH, permissions and services.
- [Docker](software/docker.md): containers and how the robot software runs in one.
- [ROS 2](software/ros2.md): nodes, topics, launch files and tf, using the robot's own packages.
- [Firmware](software/firmware.md): the ESP32-S3 control loop, the serial protocol, calibration and failsafes.
- [Kinematics and gaits](software/kinematics-and-gaits.md): leg geometry, inverse kinematics and the trot.
- [Simulation and RL](software/simulation-and-rl.md): MuJoCo, Gazebo, PPO training and the sim-to-real gap.
- [CAD as code](software/cad-as-code.md): how the robot is designed, verified and published from code.

## Making

- [3D printing](making/3d-printing.md): PETG, orientation, supports and the verified slicer profile.
- [Fasteners](making/fasteners.md): screws into printed plastic, pilot holes, engagement and threadlocker.
- [Tools and workshop](making/tools-and-workshop.md): what you need and how to solder, crimp and measure.
- [Cable management and the wiring harness](making/cable-management.md): wire sizing, fuses, service loops across the hip, bend radius, bundling, connectors and the CAD-routed cut list.
- [Strength, torque and failure](making/strength.md): torque, stress, layer tear-out, buckling, screw shear and tightening torques, worked on the robot's own parts.
- [Safety](making/safety.md): LiPo safety, first power-up, fuses and moving legs.

The [glossary](glossary.md) defines every term used on this site.
