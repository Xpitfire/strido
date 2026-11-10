# Sensors

Sensors are how the robot knows anything about itself and its surroundings. Hobby servos report nothing back, so Strido relies on four sensors: an IMU for body orientation, a 2D LiDAR for distances, a wide-angle camera for images and a power monitor for the battery. This page explains how each one works, where it sits and which software uses its data.

::: tip In Strido
| Sensor | BOM line | Connected to | ROS 2 topic | Frame |
|---|---|---|---|---|
| Adafruit LSM6DSOX 6-DoF IMU (4438) | `lsm6dsox` | XIAO, I²C 0x6A | `/imu/data` | `imu_link` |
| Slamtec RPLIDAR C1 + USB adapter | `rplidar_c1` | Pi USB, `/dev/rplidar` | `/scan` | `lidar_link` |
| Raspberry Pi Camera Module 3 Wide | `camera_module_3_wide` | Pi CSI, 22→15 pin FFC | `/camera/image_raw` | `camera_optical_frame` |
| Adafruit INA260 power monitor (4226) | `ina260` | XIAO, I²C 0x41 | `/battery_state` | — |

Field-of-view checks: `docs/verification/sensors.md`. Firmware set-up: `firmware/strido_esp32s3/src/main.cpp`.
:::

## IMU: LSM6DSOX accelerometer and gyroscope

An **IMU** (inertial measurement unit) measures motion from the inside, with no external reference. The LSM6DSOX is a 6-DoF IMU: two 3-axis MEMS sensors in one chip.

| Sensor | Measures | Unit | Strido setting |
|---|---|---|---|
| Accelerometer | specific force: gravity plus any acceleration | m/s² (g) | ±8 g range, 416 Hz output data rate |
| Gyroscope | angular velocity about each axis | rad/s (°/s) | ±1000 °/s range, 416 Hz output data rate |

The firmware reads both every 5 ms (200 Hz). Running the chip at 416 Hz means every read gets a fresh sample.

### Mounting and axes

The IMU sits in a pocket in the `electronics_deck`, chip side up with its STEMMA QT sockets towards the rear, held by two M2.5 × 6 screws. Mounted that way, its x axis points to the robot's left and its y axis to the rear. The firmware rotates every reading into the robot's `base_link` convention (x forward, y left, z up, REP-103):

$$
\begin{pmatrix} x \\ y \\ z \end{pmatrix}_\mathrm{base} = \underbrace{\begin{pmatrix} 0 & -1 & 0 \\ 1 & 0 & 0 \\ 0 & 0 & 1 \end{pmatrix}}_{\mathbf{R}_\mathrm{base,imu}} \begin{pmatrix} x \\ y \\ z \end{pmatrix}_\mathrm{imu}
$$

that is, $x_\mathrm{base} = -y_\mathrm{imu}$, $y_\mathrm{base} = x_\mathrm{imu}$, $z_\mathrm{base} = z_\mathrm{imu}$. The matrix $\mathbf{R}_\mathrm{base,imu}$ is a rotation of $+90^\circ$ about $z$; the same matrix is applied to both the accelerometer and the gyro vectors. Rotation matrices are explained in [frames and rotations](../theory/frames-and-rotations.md).

A wrong sign here would make the robot believe it is tilting the other way, the classic first bug in any balance controller.

### From two sensors to one orientation

Neither sensor alone gives a good orientation:

- **The accelerometer** at rest measures only gravity, so roll and pitch follow directly from which way "down" points. While walking, every footstep adds acceleration, so this estimate is noisy.
- **The gyroscope** is smooth and fast. Integrating angular velocity over time gives the angle change, but any small bias integrates into a steadily growing **drift**.

**Sensor fusion** combines the two: trust the gyro over short times, and let the accelerometer slowly pull the estimate back towards true "down". The simplest version is the **complementary filter** for one angle $\theta$ (say pitch), updated every time step $\Delta t$:

$$
\hat\theta_k = \alpha\left(\hat\theta_{k-1} + \omega_k\,\Delta t\right) + (1 - \alpha)\,\theta_{\mathrm{acc},k}, \qquad \theta_\mathrm{acc} = \operatorname{atan2}\!\left(-a_x,\ \sqrt{a_y^2 + a_z^2}\right)
$$

The first term integrates the gyro rate $\omega$; the second is the tilt computed from the gravity direction in the accelerometer reading $\mathbf{a}$. With $\alpha$ close to 1 the filter is a high-pass on the gyro and a low-pass on the accelerometer, which is where the name comes from: the two filters add up to one. The crossover time constant is $\tau = \alpha\,\Delta t / (1 - \alpha)$; for example $\alpha = 0.98$ at $\Delta t = 5\,\mathrm{ms}$ gives $\tau \approx 0.25\,\mathrm{s}$, so gyro drift is corrected within about a quarter of a second while footstep jolts shorter than that are smoothed out.

Strido runs a **Mahony filter** (`Adafruit_Mahony`) on the XIAO at 200 Hz, the 3D, quaternion form of the same idea. It integrates the gyro and feeds the error $\mathbf{e} = \mathbf{g}_\mathrm{meas} \times \hat{\mathbf{g}}$ between the predicted and measured gravity direction back as a correction to the rate:

$$
\boldsymbol{\omega}_\mathrm{corr} = \boldsymbol{\omega}_\mathrm{gyro} + K_\mathrm{p}\,\mathbf{e} + K_\mathrm{i} \int \mathbf{e}\,\mathrm{d}t
$$

The proportional gain $K_\mathrm{p}$ sets how hard the accelerometer pulls, and the optional integral gain $K_\mathrm{i}$ can learn a constant gyro bias. The firmware uses the library defaults: $K_\mathrm{p} = 0.5$ and $K_\mathrm{i} = 0$, so no bias learning. [State estimation](../theory/state-estimation.md) derives both filters and compares them with the Kalman filter.

The result is a **quaternion**, a four-number representation of 3D orientation that has no gimbal-lock problems. It travels in the `STATE` frame at 100 Hz and is published as `/imu/data` together with the raw gyro and acceleration.

::: warning Yaw is not observable
Gravity tells you roll and pitch but says nothing about heading (yaw). Without a magnetometer, the IMU's yaw estimate drifts. For heading over time, use the LiDAR (scan matching / SLAM).
:::

### Who uses it

- **`policy_node`** (learned controller) turns the quaternion into the gravity direction in the body frame and feeds it, with the gyro rates, into the policy's observation every 50 Hz step. It does not start until it has seen IMU data.
- **`strido-cli monitor`** shows roll and pitch on the bench.
- **`mcu_bridge`** never publishes a fake upright orientation: if the IMU reports a fault (`imu_ok` false), `/imu/data` is simply not published.

## LiDAR: RPLIDAR C1

A **2D LiDAR** spins a laser rangefinder and measures the distance to the nearest object at each angle in one horizontal plane. The C1 measures **time of flight** (DTOF): it times how long a 905 nm infrared laser pulse takes to come back.

| Specification (Slamtec datasheet) | Value |
|---|---|
| Range | 0.05–12 m (white target), 0.05–6 m (black target) |
| Sample rate | 5000 samples/s |
| Scan frequency | 10 Hz typical (8–12 Hz) |
| Angular resolution | 0.72° at 10 Hz |
| Accuracy | ±30 mm |
| Interface | 3.3 V TTL UART, 460 800 baud (here via a USB adapter) |
| Supply | 5 V, about 230 mA running, about 800 mA at start-up |
| Laser safety | IEC 60825 Class 1 |

The numbers fit together: $\dfrac{5000\,\mathrm{samples/s}}{10\,\mathrm{scans/s}} = 500$ points per scan, and $360^\circ / 500 = 0.72^\circ$ between points. Time of flight turns into distance as $d = c\,\Delta t / 2$ (the light travels out and back); at the 12 m maximum range the round trip lasts only $\Delta t = 2d/c \approx 80\,\mathrm{ns}$.

### Placement

A LiDAR sees nothing below or above its scan plane, and anything of the robot's own that crosses the plane blinds part of the scan. Strido lifts the C1 on a 14 mm `lidar_pedestal` on `top_shell_sensor`. Its scan plane sits 71.6 mm above the hip axes, about 254 mm above ground when standing at 170 mm. The ray-cast check in `docs/verification/sensors.md` blocks **0 of 720** test rays in every pose: stand, crouch, trot swing apex, maximum stride and hips abducted.

### Who uses it

`sllidar_ros2` publishes `/scan` (`sensor_msgs/LaserScan`) at 10 Hz in `lidar_link`. The `/scan` topic follows the Go2 conventions, so standard ROS 2 tools run unchanged: SLAM to build a map, Nav2 for obstacle avoidance and path planning. This matters because `gait_node`'s `/odom` integrates only the *commanded* velocity (dead reckoning, no slip model). For real navigation, a LiDAR-based odometry or SLAM source should replace it (`gait_node.py` docstring).

## Camera: Camera Module 3 Wide

| Specification (Raspberry Pi product brief) | Value |
|---|---|
| Sensor | Sony IMX708, 11.9 MP (4608 × 2592), back-illuminated, stacked |
| Lens | 2.75 mm, F2.2 |
| Field of view | 120° diagonal, 102° horizontal, 67° vertical |
| Focus | phase-detection autofocus, 5 cm to infinity |
| Video modes | 1080p50, 720p100, 480p120 |
| Interface | MIPI CSI-2, 15-pin 1 mm FPC |

The **Wide** variant was chosen because a small robot close to the ground sees more of its surroundings with a 102° horizontal view than with the standard module's 66°.

### Placement

The camera sits on a tilting mount (`camera_mount_base` and `camera_tilt_plate`) on the flat top of the front shell. An M3 × 40 pivot with a lock nut gives a friction tilt. The first design put the camera on the top shell, where the ray-cast check found the robot's own nose filling **42 %** of the image. The new position shows **0 %** in every checked pose (`docs/design.md`, `docs/verification/sensors.md`).

### Who uses it

`camera_ros` publishes `/camera/image_raw` in `camera_optical_frame`. On the Pi 5 the camera needs the Raspberry Pi fork of libcamera, so the node is built on the host and enabled with `camera:=true` (default false; the Docker image has no camera node). The camera is there for your own perception nodes: teleoperation video, object detection, visual navigation.

## Power monitor: INA260

The INA260 measures **voltage and current** with a built-in 2 mΩ shunt resistor, 1.25 mA current resolution, up to 15 A and 36 V. In Strido it sits high-side in the logic branch (see [Power](power.md)):

- **Bus voltage = pack voltage** (minus tiny losses). The firmware reads it every 100 ms. It warns at 6.8 V and relaxes the servos after 5 consecutive readings below 6.4 V.
- **Current = logic-branch current only.** The servo current bypasses it.

`mcu_bridge` publishes both as `/battery_state` (`sensor_msgs/BatteryState`, technology LiPo, negative current = discharging). The firmware refuses to drive the servos without it, because a robot with no voltage sensor can drain its LiPo into damage.

## Summary: sensor to software

| Sensor | Read by | Rate | Software that uses it |
|---|---|---|---|
| LSM6DSOX | XIAO, I²C | 200 Hz, published at 100 Hz | Mahony filter → `/imu/data` → `policy_node`, monitoring |
| INA260 | XIAO, I²C | 10 Hz | low-battery warning and cut-off, `/battery_state` |
| RPLIDAR C1 | Pi, USB serial | 10 Hz scans | `/scan` → SLAM, Nav2, obstacle avoidance |
| Camera Module 3 Wide | Pi, CSI | video rate | `/camera/image_raw` → your perception nodes |

## Check yourself

1. Why can the accelerometer alone not give a reliable orientation while the robot trots?
2. In the Mahony filter, what does the proportional gain decide, and what would a non-zero integral gain add?
3. How many points does one C1 scan contain at 10 Hz, and what is their angular spacing?
4. Why was the camera moved from the top shell to the front shell?
5. Which robot heading information can the IMU *not* provide, and which sensor fills the gap?

<details>
<summary>Answers</summary>

1. While moving, it measures footstep accelerations on top of gravity, so the "down" direction it reports is noisy.
2. The proportional gain decides how strongly the accelerometer's gravity direction pulls the gyro-integrated estimate back. A non-zero integral gain would also learn a constant gyro bias; Strido leaves it at 0.
3. $5000 / 10 = 500$ points, $0.72^\circ$ apart.
4. On the top shell the robot's nose filled 42 % of the image; on the front shell it fills 0 %.
5. Yaw (heading) is not observable from gravity and drifts; the LiDAR (scan matching or SLAM) provides it.

</details>

## Further reading

- [LSM6DSOX product page (STMicroelectronics)](https://www.st.com/en/mems-and-sensors/lsm6dsox.html)
- [Adafruit LSM6DSOX guide](https://learn.adafruit.com/lsm6dsox-and-ism330dhc-6-dof-imu)
- [RPLIDAR C1 datasheet (Slamtec)](https://wiki.slamtec.com/download/attachments/83066883/SLAMTEC_rplidar_datasheet_C1_v1.0_en.pdf?api=v2&modificationDate=1700531479533&version=1)
- [Camera Module 3 product brief (Raspberry Pi)](https://pip.raspberrypi.com/documents/RP-008151-DS-camera-module-3-product-brief.pdf)
- [Open-source IMU and AHRS algorithms (x-io, includes Mahony)](https://x-io.co.uk/open-source-imu-and-ahrs-algorithms/)
- Related pages: [Buses](buses.md), [Power](power.md), [ROS 2](../software/ros2.md), [Kinematics and gaits](../software/kinematics-and-gaits.md)
- Theory: [Frames and rotations](../theory/frames-and-rotations.md), [State estimation](../theory/state-estimation.md)
