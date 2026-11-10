# State estimation

A robot never measures its state directly; it infers orientation, velocity and position from noisy, biased sensors. This page covers IMU models, complementary and Mahony filters, the Kalman filter, leg odometry and LiDAR SLAM, and what Strido actually publishes.

::: tip In Strido
The XIAO ESP32-S3 reads an LSM6DSOX IMU and runs a Mahony filter in its $200\,\mathrm{Hz}$ control loop (`firmware/strido_esp32s3/src/main.cpp`, period `kControlPeriodUs = 5000` in `board_config.h`). `ros2/strido_control/strido_control/mcu_bridge.py` republishes it as `/imu/data`; `gait_node.py` publishes `/odom` by dead reckoning; an RPLIDAR C1 publishes `/scan` (see [docs/software.md](../../software.md) and [Sensors](../hardware/sensors.md)).
:::

## IMU measurement models

An inertial measurement unit contains a 3-axis **gyroscope** (angular velocity) and a 3-axis **accelerometer** (specific force). Both are expressed in the sensor's body frame $\{b\}$.

**Gyroscope.**

$$
\tilde{\boldsymbol{\omega}} = \boldsymbol{\omega} + \mathbf{b}_g + \mathbf{n}_g
$$

$\mathbf{b}_g$ is a slowly drifting **bias** (temperature dependent), $\mathbf{n}_g$ white noise. Integrating the gyro gives orientation, but integrating the bias gives an angle error growing linearly in time: a bias of only $0.5^\circ/\mathrm{s}$ becomes $30^\circ$ after a minute.

**Accelerometer.** It measures acceleration *minus* gravity, rotated into the body:

$$
\tilde{\mathbf{a}} = \mathbf{R}^\top \left( \ddot{\mathbf{p}} - \mathbf{g} \right) + \mathbf{b}_a + \mathbf{n}_a, \qquad \mathbf{g} = (0, 0, -9.81)^\top\,\mathrm{m/s^2}
$$

where $\mathbf{R}$ rotates body to world. Standing still ($\ddot{\mathbf{p}} = 0$), it reads $\mathbf{R}^\top (0, 0, 9.81)^\top$: the "up" vector in body coordinates. That fixes **roll and pitch** with no drift, but it is noisy and corrupted whenever the body accelerates (every footstep). It says nothing about **yaw**, because rotating about gravity leaves the gravity vector unchanged.

The two sensors are complementary: gyro is smooth but drifts; accelerometer is noisy but drift-free.

## The complementary filter

For one tilt angle $\theta$, blend the integrated gyro (trusted at high frequency) with the accelerometer angle (trusted at low frequency):

$$
\hat{\theta}_k = \alpha \left( \hat{\theta}_{k-1} + \tilde{\omega}_k\, \Delta t \right) + (1 - \alpha)\, \theta_{\mathrm{acc},k}, \qquad \theta_{\mathrm{acc}} = \operatorname{atan2}(\tilde{a}_y, \tilde{a}_z)
$$

In the frequency domain this is a high-pass on the gyro plus a low-pass on the accelerometer with the same cut-off; the crossover time constant is

$$
\tau = \frac{\alpha\, \Delta t}{1 - \alpha}
$$

**Worked example.** At Strido's $\Delta t = 5\,\mathrm{ms}$, choosing $\alpha = 0.98$ gives $\tau = 0.98 \times 0.005 / 0.02 \approx 0.25\,\mathrm{s}$: longer than the $0.2\,\mathrm{s}$ stance of the trot, so footstep jolts are mostly filtered out while gyro drift is corrected within about a second.

## The Mahony filter (what the firmware runs)

Mahony's filter is a complementary filter on the rotation group, using a quaternion $\hat{\mathbf{q}}$ instead of separate angles. Each step:

1. Predict the gravity ("up") direction from the current estimate: $\hat{\mathbf{v}} = \hat{\mathbf{R}}^\top \mathbf{e}_z$.
2. Normalise the accelerometer: $\bar{\mathbf{a}} = \tilde{\mathbf{a}} / \lVert \tilde{\mathbf{a}} \rVert$.
3. The error is the rotation needed to align them:

$$
\mathbf{e} = \bar{\mathbf{a}} \times \hat{\mathbf{v}}
$$

4. Correct the gyro with proportional and integral feedback (the integral term converges to minus the gyro bias, cancelling it):

$$
\mathbf{b}_{k} = \mathbf{b}_{k-1} + K_i\, \mathbf{e}\, \Delta t, \qquad \boldsymbol{\omega}_\mathrm{c} = \tilde{\boldsymbol{\omega}} + K_p\, \mathbf{e} + \mathbf{b}_k
$$

5. Integrate the quaternion kinematics $\dot{\mathbf{q}} = \tfrac12\, \mathbf{q} \otimes (0, \boldsymbol{\omega}_\mathrm{c})$ and renormalise:

$$
\hat{\mathbf{q}}_k = \frac{\hat{\mathbf{q}}_{k-1} + \tfrac12\, \hat{\mathbf{q}}_{k-1} \otimes (0, \boldsymbol{\omega}_\mathrm{c})\, \Delta t}{\lVert \cdot \rVert}
$$

$K_p$ sets the crossover (roughly $\tau \approx 1/K_p$); $K_i$ removes constant gyro bias. Yaw is not observable without a magnetometer, so it drifts.

In the firmware, `Adafruit_Mahony` is started at $1/\Delta t = 200\,\mathrm{Hz}$ and fed through `updateIMU` (gyro and accelerometer only, no magnetometer). Before filtering, board axes are remapped to the base frame because the IMU is mounted with its $x$ to robot left and $y$ to the rear:

$$
(\omega_x, \omega_y, \omega_z) = (-\tilde{\omega}_y, \tilde{\omega}_x, \tilde{\omega}_z), \qquad (a_x, a_y, a_z) = (-\tilde{a}_y, \tilde{a}_x, \tilde{a}_z)
$$

The sensor is configured for $\pm 8\,g$, $\pm 1000^\circ/\mathrm{s}$ at $416\,\mathrm{Hz}$ output data rate. The repository keeps the library's default gains (Adafruit AHRS: $K_p = 0.5$, $K_i = 0$, i.e. no bias integration).

## The Kalman filter

The Kalman filter is the optimal estimator for linear systems with Gaussian noise. State $\mathbf{x}$ with covariance $\mathbf{P}$, model

$$
\mathbf{x}_k = \mathbf{F} \mathbf{x}_{k-1} + \mathbf{B} \mathbf{u}_k + \mathbf{w}_k, \quad \mathbf{w} \sim \mathcal{N}(0, \mathbf{Q}); \qquad \mathbf{z}_k = \mathbf{H} \mathbf{x}_k + \mathbf{v}_k, \quad \mathbf{v} \sim \mathcal{N}(0, \mathbf{R}_\mathrm{n})
$$

**Predict** (propagate the model; uncertainty grows):

$$
\hat{\mathbf{x}}_{k \mid k-1} = \mathbf{F} \hat{\mathbf{x}}_{k-1} + \mathbf{B} \mathbf{u}_k, \qquad \mathbf{P}_{k \mid k-1} = \mathbf{F} \mathbf{P}_{k-1} \mathbf{F}^\top + \mathbf{Q}
$$

**Update** (fuse a measurement; uncertainty shrinks):

$$
\mathbf{K}_k = \mathbf{P}_{k \mid k-1} \mathbf{H}^\top \left( \mathbf{H} \mathbf{P}_{k \mid k-1} \mathbf{H}^\top + \mathbf{R}_\mathrm{n} \right)^{-1}
$$

$$
\hat{\mathbf{x}}_k = \hat{\mathbf{x}}_{k \mid k-1} + \mathbf{K}_k \left( \mathbf{z}_k - \mathbf{H} \hat{\mathbf{x}}_{k \mid k-1} \right), \qquad \mathbf{P}_k = (\mathbf{I} - \mathbf{K}_k \mathbf{H})\, \mathbf{P}_{k \mid k-1}
$$

The gain $\mathbf{K}$ weighs the innovation $\mathbf{z} - \mathbf{H}\hat{\mathbf{x}}$ by how much we trust the measurement ($\mathbf{R}_\mathrm{n}$) versus the prediction ($\mathbf{P}$). A tilt filter with state $(\theta, b_g)$, gyro as input and accelerometer angle as measurement converges to a complementary filter with an automatically tuned $\alpha$ and bias estimate. Nonlinear systems (rotations, legged robots) use the **extended** Kalman filter, which linearises $\mathbf{F}$ and $\mathbf{H}$ about the current estimate.

## Leg odometry

If a stance foot does not slip, its world position is fixed, so the body velocity follows from the leg's joint velocities through forward kinematics (see [Kinematics](kinematics.md)):

$$
\mathbf{v}_\mathrm{body} = -\left( \mathbf{J}(\mathbf{q})\, \dot{\mathbf{q}} + \boldsymbol{\omega} \times \mathbf{p}_\mathrm{foot} \right)
$$

averaged over the stance feet and integrated for position. Errors come from slip, contact detection and calibration, so it drifts; state-of-the-art quadrupeds fuse it with the IMU in an EKF.

Strido's hobby servos have **no position feedback**: `/joint_states` reports the commanded angles after clamping, not measured ones. True leg odometry is therefore not available, and `gait_node.py` does something simpler: it integrates the *commanded* body velocity,

$$
x_{k} = x_{k-1} + (v_x \cos\psi - v_y \sin\psi)\, \Delta t, \quad y_{k} = y_{k-1} + (v_x \sin\psi + v_y \cos\psi)\, \Delta t, \quad \psi_k = \psi_{k-1} + \omega_z \Delta t
$$

with no slip model. If the robot actually achieves 80 % of a $0.30\,\mathrm{m/s}$ command, `/odom` overestimates distance by $0.06\,\mathrm{m}$ every second.

## LiDAR scan matching and SLAM

A 2D LiDAR returns ranges $r_j$ at bearings $\theta_j$. **Scan matching** finds the rigid transform $(\mathbf{R}, \mathbf{t})$ that best aligns a new scan to a previous scan or map, e.g. with ICP (iterative closest point):

$$
(\mathbf{R}^\star, \mathbf{t}^\star) = \arg\min_{\mathbf{R}, \mathbf{t}} \sum_j \left\lVert \mathbf{R} \mathbf{p}_j + \mathbf{t} - \mathbf{m}_{c(j)} \right\rVert^2
$$

where $\mathbf{m}_{c(j)}$ is the closest map point to $\mathbf{p}_j$. Chaining matches gives LiDAR odometry, which also drifts. **SLAM** (simultaneous localisation and mapping) removes the drift by recognising previously seen places (*loop closure*) and solving a pose-graph optimisation over all poses at once. Wheel/leg odometry is a useful initial guess for the matcher, which is the role the code comment assigns to Strido's `/odom` ("a seed for SLAM").

## What Strido publishes

| Topic | Contents | Source |
|---|---|---|
| `/imu/data` (`sensor_msgs/Imu`, frame `imu_link`, axes aligned with `base_link`) | orientation quaternion from the Mahony filter, angular velocity in $\mathrm{rad/s}$, linear acceleration in $\mathrm{m/s^2}$ (gravity included); not published while the IMU reports a fault | `mcu_bridge.py`, state stream at $100\,\mathrm{Hz}$ (`kStatePeriodMs = 10`) |
| `/odom` + TF `odom` $\to$ `base_link` (`nav_msgs/Odometry`) | dead reckoning of the commanded velocity | `gait_node.py` only |
| `/scan` (`sensor_msgs/LaserScan`, `lidar_link`) | RPLIDAR C1 ranges at $10\,\mathrm{Hz}$ | `sllidar_ros2` |

The learned policy uses only `/imu/data`: the gyro and the gravity direction derived from the quaternion (see [Reinforcement learning](reinforcement-learning.md)).

## Check yourself

1. Why can an accelerometer give roll and pitch but not yaw?
   <details><summary>Answer</summary>

   It measures the gravity direction in the body frame; rotating about the vertical axis does not change that direction.

   </details>
2. With $\Delta t = 5\,\mathrm{ms}$, what $\alpha$ gives a complementary-filter time constant of $0.5\,\mathrm{s}$?
   <details><summary>Answer</summary>

   $\alpha/(1-\alpha) = 100$, so $\alpha = 100/101 \approx 0.990$.

   </details>
3. What does the integral gain $K_i$ in the Mahony filter estimate, and what happens with $K_i = 0$?
   <details><summary>Answer</summary>

   The gyro bias. With $K_i = 0$ a constant bias leaves a small steady roll/pitch offset of about $b_g/K_p$ and uncorrected yaw drift.

   </details>
4. In the Kalman update, what happens to $\mathbf{K}$ as $\mathbf{R}_\mathrm{n} \to \infty$?
   <details><summary>Answer</summary>

   $\mathbf{K} \to 0$: the measurement is ignored and the estimate follows the prediction.

   </details>
5. Why can't Strido do classic leg odometry?
   <details><summary>Answer</summary>

   Its servos give no joint-position feedback, so the actual $\mathbf{q}$ and $\dot{\mathbf{q}}$ are unknown; only commands are available.

   </details>

## Further reading

- R. Mahony, T. Hamel and J.-M. Pflimlin, "Nonlinear Complementary Filters on the Special Orthogonal Group", *IEEE Transactions on Automatic Control*, 2008.
- S. Thrun, W. Burgard and D. Fox, *Probabilistic Robotics*, MIT Press, 2005.
- J. Solà, "Quaternion kinematics for the error-state Kalman filter", arXiv:1711.02508, 2017.
- M. Bloesch et al., "State Estimation for Legged Robots — Consistent Fusion of Leg Kinematics and IMU", *Robotics: Science and Systems*, 2012.
- W. Hess, D. Kohler, H. Rapp and D. Andor, "Real-Time Loop Closure in 2D LIDAR SLAM" (Cartographer), *IEEE ICRA*, 2016.
