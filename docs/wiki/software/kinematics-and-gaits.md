# Kinematics and gaits

Kinematics is the geometry of motion: given joint angles, where is the foot (forward kinematics), and given a foot position, which joint angles put it there (inverse kinematics). A gait is the rhythm in which the four feet lift, swing and push. This page works through both for the Strido leg, using the code that actually drives the robot.

::: tip In Strido
- **Leg kinematics and knee linkage:** `packages/strido-core/src/strido/leg.py` (Python) and its C++ mirror `firmware/strido_esp32s3/lib/strido_core/src/kinematics.cpp` + `servo_map.cpp`.
- **Gait:** `packages/strido-core/src/strido/gait.py` (`TrotGait`, `GaitConfig`, `stand_pose`, `clamp_leg`), used unchanged by `gait_node` (ROS 2), `strido_sim.walk` (MuJoCo) and as the stand pose for the learned policy.
- **Dimensions and limits:** measured from the CAD into `hardware/kinematics.yaml` and `hardware/joint_limits.yaml`, then generated into `packages/strido-core/src/strido/geometry.py` and `geometry_generated.h` ([CAD as code](cad-as-code.md)).
- **Servos:** 12 × SPT5435LV-180W position servos ([servos](../hardware/servos.md)).
:::

## The leg

Each leg has three joints, named and signed like the Unitree Go2 so that tools and policies transfer:

| Joint | Axis | Zero | Positive direction | Actuated by |
|---|---|---|---|---|
| hip (q1) | +x (forward) | leg vertical | foot moves to +y (left) | hip servo, direct |
| thigh (q2) | +y | femur straight down | knee moves backwards | thigh servo, direct (coaxial with the femur pivot) |
| calf (q3) | +y, relative to the femur | calf in line with femur | negative = knee bent | knee servo, **through two linkages** |

Measured dimensions (front-left leg, generated values rounded):

| Quantity | Value |
|---|---|
| Hip axis position in `base_link` | x = ±0.120 m, y = ±0.039 m |
| Lateral offset hip axis → leg plane (`thigh_offset_y`) | 0.038 m front, 0.040 m rear |
| Thigh (femur) length l1 | 0.130 m |
| Calf (tibia) length l2, to foot centre | 0.124 m |
| Foot sphere radius | 0.012 m |

Full extension is $l_1 + l_2 \approx 0.254\,\mathrm{m}$; the robot stands with the hip axes 0.17 m above the foot centres.

### The knee linkage

The knee servo does not sit at the knee: it is up in the leg module. It turns an arm; a **parallelogram** (arm 24 mm, short link 28.3 mm, crank) copies the arm angle onto a crank coaxial with the femur pivot; a **four-bar** (crank 26.9 mm, long link 131 mm, tibia crank 24 mm, femur) turns the tibia. Keeping the servo mass near the body makes the leg lighter to swing.

The cost: the knee angle $q_3$ depends on **both** the crank angle $\psi$ and the thigh angle $q_2$. Moving only the thigh servo also changes the knee angle. So software must solve the linkage:

- `crank_from_calf(leg, q2, q3)` gives the crank angle the knee servo must hold (inverse linkage), by intersecting two circles: one around the femur pivot with the crank radius, one around the tibia pin with the long-link length.
- `calf_from_crank(leg, q2, ψ)` is the forward linkage.

Two circles intersect in two points; the code picks the branch the CAD assembly is in (`_branches`), so the solver never flips to the mirror configuration.

**Transmission angle** is the angle between the long link and the crank (or tibia crank). Near 0° or 180° the linkage is near a singularity: a small servo motion produces a huge knee motion and the servo loses leverage. The range-of-motion sweep keeps it at or above 25°; in the standing pose it is about 84–86°, close to the ideal 90°.

## Forward kinematics

`foot_position(name, q)` in `leg.py`:

1. In the leg plane ($u$ forward, $v$ up, origin at the thigh pivot):

   $$
   \mathbf{p}_\mathrm{knee} = \begin{pmatrix} -l_1 \sin q_2 \\ -l_1 \cos q_2 \end{pmatrix}, \qquad
   \mathbf{p}_\mathrm{foot} = \mathbf{p}_\mathrm{knee} + \begin{pmatrix} -l_2 \sin(q_2 + q_3) \\ -l_2 \cos(q_2 + q_3) \end{pmatrix}
   $$

   The calf's absolute angle is $q_2 + q_3$ because $q_3$ is measured relative to the femur: angles of a serial chain add.

2. Place the plane point at lateral offset `thigh_offset_y`, rotate it about $x$ by the hip angle $q_1$, then add the hip position in `base_link`: $\mathbf{p} = \mathbf{p}_\mathrm{hip} + \mathbf{R}_x(q_1)\,(u,\ d_y,\ v)^\top$. The general method (homogeneous transforms) is in [kinematics](../theory/kinematics.md) and [frames and rotations](../theory/frames-and-rotations.md).

Example from the code: the stand pose for the front-left leg is $\mathbf{q} = (0,\ 0.812,\ -1.676)\,\mathrm{rad} = (0^\circ,\ 46.5^\circ,\ -96.0^\circ)$, and forward kinematics returns the foot at $(0.120,\ 0.077,\ -0.170)\,\mathrm{m}$: right under the hip, 0.170 m down. Check the height in the plane: $v = -0.130\cos(0.812) - 0.124\cos(0.812 - 1.676) \approx -0.089 - 0.081 = -0.170\,\mathrm{m}$. The $y$ value 0.077 m is the hip's 0.039 m plus the 0.038 m leg-plane offset.

## Inverse kinematics

`inverse_kinematics(name, foot)` solves the reverse, analytically (no iteration):

1. **Hip.** Look at the leg from the front. The foot must lie on a circle of radius $d_y$ (`thigh_offset_y`) around the hip axis plus a "depth" $d$ along the leg, by Pythagoras: $d = \sqrt{y^2 + z^2 - d_y^2}$. The hip angle is the rotation that aligns the leg plane with the foot: $q_1 = \operatorname{atan2}(z, y) - \operatorname{atan2}(-d, d_y)$.
2. **Knee from the law of cosines.** In the leg plane the foot is at $(u, v) = (x, -d)$. The triangle thigh–calf–(pivot to foot) has sides $l_1$, $l_2$ and $r = \sqrt{u^2 + v^2}$, so $r^2 = l_1^2 + l_2^2 + 2 l_1 l_2 \cos q_3$, which gives

   $$
   \cos q_3 = \frac{u^2 + v^2 - l_1^2 - l_2^2}{2\, l_1 l_2}, \qquad q_3 = -\arccos(\cos q_3)
   $$

   (negative: the knee bends backwards). If $\lvert \cos q_3 \rvert > 1$ the target is out of reach and the function returns `None`.
3. **Thigh.** The direction to the foot minus the angle the bent calf adds:

   $$
   q_2 = \operatorname{atan2}(-u, -v) - \operatorname{atan2}\left(l_2 \sin q_3,\ l_1 + l_2 \cos q_3\right)
   $$

Then `clamp_leg` applies the joint limits and the knee-crank window. If the crank needed is outside its window, it is clamped and the calf angle recomputed from the clamped crank: the firmware does exactly the same in actuator space, so simulation and robot agree.

## Joint limits

Generated from the CAD range-of-motion sweep (collisions with all parts, a mirrored partner leg with 0.3 mm clearance, transmission angle ≥ 25°, and ±85° servo travel around the assembly neutral):

| Joint | FL | FR | RL | RR |
|---|---|---|---|---|
| Hip | −17.5…50° | −50…17.5° | −17.5…45° | −45…17.5° |
| Thigh | −40…125° | −40…125° | −15…125° | −15…125° |
| Calf | −150…−45° | −150…−45° | −150…−45° | −150…−45° |
| Knee crank | −2.5…75° | −2.5…75° | −2.5…75° | −2.5…75° |

The inward hip limits (±17.5°) are small because both front (and both rear) feet could otherwise meet under the body (ADR-005 in [decisions](../../decisions.md)). The front thigh sweep allowed −45°, but the servo can only reach −40° within ±85° of its 45° neutral. Limits are applied in three places (gait, policy environment, firmware) from the same generated numbers.

## From angles to servo pulses

Joint space and servo space differ only for the knee: hip and thigh servos hold $q_1$ and $q_2$ directly, the knee servo holds the crank angle $\psi$. The firmware then maps each actuator angle $\theta$ to a pulse width $t_\mathrm{p}$, with calibration sign $s$ (`direction`), `neutral_us` $t_\mathrm{neutral}$ and reference angle $\theta_0$ (`zero_rad`):

$$
t_\mathrm{p} = t_\mathrm{neutral} + s \cdot \frac{2000\,\mu\mathrm{s}}{\pi\,\mathrm{rad}} \cdot (\theta - \theta_0)
$$

with per-joint calibration from flash ([firmware](firmware.md)). At the assembly reference (all servos at 1500 µs) the legs are vertical in abduction, the femur is 45° backwards and the knee crank at 35°.

## Gaits: stance, swing and the gait cycle

A gait repeats with a **period** $T$. Each leg spends a fraction of it on the ground (**stance**, pushing the body) and the rest in the air (**swing**, moving forward to its next foothold). The stance fraction is the **duty factor** $\beta = T_\mathrm{stance}/T$. **Phase offsets** say when each leg starts its cycle. The theory behind gaits, support polygons and Raibert foot placement is in [legged locomotion](../theory/legged-locomotion.md).

| Gait | Duty factor | Phase pattern | Character |
|---|---|---|---|
| Walk | ≥ 0.75 | one leg at a time (e.g. FL, RR, FR, RL) | at least three feet down: statically stable, slow |
| Trot | 0.5 | diagonal pairs together (FL+RR, then FR+RL) | two feet down: needs momentum and a short period; robust and simple |

**Static stability:** a robot standing still does not fall if its centre of mass projects inside the **support polygon** formed by the feet on the ground. With three feet down (walk) that triangle can be kept under the body. With two diagonal feet (trot) the polygon is a line, so the body is briefly unsupported in roll and pitch; a 0.4 s cycle switches pairs before it tips noticeably.

**Strido implements a trot only** (`TrotGait`, `PHASE_OFFSET = {"FL": 0.0, "RR": 0.0, "FR": 0.5, "RL": 0.5}`). A walk would need a new phase table and a duty factor ≥ 0.75; nothing in the repo provides one.

### The trot in numbers

`GaitConfig` defaults:

| Parameter | Value |
|---|---|
| `body_height` | 0.17 m |
| `period` | 0.40 s (2.5 steps per second per leg pair) |
| `duty` | 0.5 (0.2 s stance, 0.2 s swing) |
| `step_height` | 0.035 m swing apex |
| `max_linear` | 0.30 m/s forward, 0.15 m/s sideways |
| `max_yaw_rate` | 1.0 rad/s |

How `foot_targets()` places each foot:

1. **Per-leg velocity.** For body command $(v_x, v_y, \omega_z)$, a foot at $(x, y)$ must move at $\mathbf{v}_\mathrm{foot} = (v_x - \omega_z y,\ v_y + \omega_z x)$, the planar form of $\mathbf{v} + \boldsymbol{\omega} \times \mathbf{r}$: turning on the spot makes the left feet move backward and the right feet forward.
2. **Stride** = velocity × stance time, $L = v\,\beta T$. At 0.15 m/s: $0.15\,\mathrm{m/s} \times 0.2\,\mathrm{s} = 0.03\,\mathrm{m}$. At the 0.30 m/s limit: 0.06 m.
3. **Stance** (phase $< \beta$): the foot slides from $+L/2$ to $-L/2$ relative to its nominal position at body speed, so the body moves forward over it.
4. **Swing**: the foot returns from $-L/2$ to $+L/2$ and lifts on a half-sine, $h(s) = 0.035\,\mathrm{m} \cdot \sin(\pi s)$ with swing progress $s \in [0, 1]$. Landing half a stride ahead of the hip is the Raibert-style foot placement: the touchdown point is symmetric about the hip, so the stance phase neither accelerates nor brakes the body on average.
5. **Inverse kinematics** turns the four foot targets into 12 angles, then `clamp_leg` applies the limits.

With a zero command the feet stay at their nominal positions: the robot stands still rather than trotting in place.

`gait_node` adds a ramp (velocity changes at most 0.5 m/s² and 0.5 rad/s²) and a smooth 3 s stand-up from the rest pose (0.07 m: thigh 69.4°, calf −148.1°) to the stand pose.

This gait is **open-loop**: it does not read the IMU and makes no balance corrections. It works because the trot is short-period and the robot is light (3.01 kg). The learned policy ([simulation and RL](simulation-and-rl.md)) is the closed-loop alternative: it observes the IMU.

## PD control: what holds a joint at its target

A position servo is a small feedback controller. The usual model is a **PD** (proportional-derivative) law:

$$
\tau = k_\mathrm{p}\,(q_\mathrm{target} - q) - k_\mathrm{d}\,\dot q
$$

The P term pulls towards the target like a spring; the D term damps motion like a shock absorber. Large $k_\mathrm{p}$ gives stiff, accurate joints but can oscillate; $k_\mathrm{d}$ suppresses the oscillation. For a joint with inertia $I$ the closed loop is a mass–spring–damper, $I\ddot q + k_\mathrm{d}\dot q + k_\mathrm{p} q = k_\mathrm{p} q_\mathrm{target}$, with natural frequency $\omega_n = \sqrt{k_\mathrm{p}/I}$ and damping ratio $\zeta = k_\mathrm{d} / (2\sqrt{k_\mathrm{p} I})$; see [control](../theory/control.md).

In Strido:

- **On the robot** the PD loop lives *inside each SPT5435LV*: its electronics compare the commanded pulse with an internal potentiometer and drive the motor. The ESP32 sends only targets; nothing outside the servo knows the real angle or torque.
- **In MuJoCo** each servo is a position actuator with $k_\mathrm{p} = 25\,\mathrm{N\,m/rad}$, $k_\mathrm{v} = 0.4\,\mathrm{N\,m\,s/rad}$ and a torque limit of $\pm 3.43\,\mathrm{N\,m}$, the SPT5435LV stall torque at 6 V. So 0.1 rad of error gives $25 \times 0.1 = 2.5\,\mathrm{N\,m}$; beyond $3.43 / 25 \approx 0.14\,\mathrm{rad}$ the servo saturates, as a real one would.
- **In Gazebo** `gz_ros2_control` exposes a `position` command interface per joint, driven by `leg_controller` (`position_controllers/JointGroupPositionController`, 200 Hz).

These gains are modelling estimates; [simulation](../../simulation.md) notes they should be refitted to measured servo response once a robot exists.

## Check yourself

1. Why does moving only the thigh servo also change the knee angle?
2. Using the law of cosines, what is $\cos q_3$ for a foot at full extension (distance $l_1 + l_2$)?
3. What is the stride length at 0.20 m/s with the default trot?
4. Why is a trot not statically stable, and why does it still work?
5. In MuJoCo, what torque does a joint produce at 0.05 rad error and zero velocity?

<details>
<summary>Answers</summary>

1. The knee servo drives the tibia through a parallelogram and four-bar attached to the femur; the knee angle depends on the crank angle and the thigh angle.
2. $(l_1 + l_2)^2 - l_1^2 - l_2^2 = 2 l_1 l_2$, so $\cos q_3 = 1$ and $q_3 = 0$: the leg is straight (and the calf limit $-45^\circ$ forbids it).
3. $0.20\,\mathrm{m/s} \times 0.2\,\mathrm{s} = 0.04\,\mathrm{m}$.
4. Only two diagonal feet support the body, so the centre of mass is not inside a support polygon; the short 0.4 s period switches pairs before the body tips far.
5. $25\,\mathrm{N\,m/rad} \times 0.05\,\mathrm{rad} = 1.25\,\mathrm{N\,m}$ (below the 3.43 N·m limit).

</details>

## Further reading

- [Modern Robotics (Lynch and Park), free textbook and videos](https://hades.mech.northwestern.edu/index.php/Modern_Robotics)
- [M. H. Raibert, Legged Robots That Balance (MIT Press)](https://mitpress.mit.edu/9780262681193/legged-robots-that-balance/)
- [MuJoCo XML reference: position actuators](https://mujoco.readthedocs.io/en/stable/XMLreference.html#actuator-position)
- [ros2_control: position controllers](https://control.ros.org/jazzy/doc/ros2_controllers/position_controllers/doc/userdoc.html)
- Theory: [Frames and rotations](../theory/frames-and-rotations.md), [Kinematics](../theory/kinematics.md), [Legged locomotion](../theory/legged-locomotion.md), [Control](../theory/control.md)
