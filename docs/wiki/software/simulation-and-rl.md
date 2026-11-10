# Simulation and reinforcement learning

A simulator lets you walk the robot thousands of times without breaking a part; reinforcement learning (RL) lets the computer discover a walking controller by trial and error inside that simulator. Strido uses MuJoCo for fast physics and training, Gazebo for testing the complete ROS 2 stack, and PPO to train a walking policy that runs on the Pi with plain NumPy.

::: tip In Strido
- **MuJoCo model:** `models/mujoco/strido.xml` + `scene.xml`, generated from the CAD by `make models`.
- **Gazebo model:** `ros2/strido_description/urdf/strido.urdf.xacro` (with `sim:=true`), world `ros2/strido_bringup/worlds/flat.sdf`, launched by `gazebo.launch.py`.
- **RL code:** `packages/strido-sim/src/strido_sim/rl/` (`env.py`, `train.py`, `evaluate.py`); policy runtime `packages/strido-core/src/strido/policy.py`.
- **Released policy:** `models/policies/ppo-v1/policy.npz` (MLP 23 → 128 → 128 → 12).
- **Commands:** `make sim-walk`, `make sim-gazebo`, `make rl-smoke`, `make rl-train`, `make rl-eval` ([simulation](../../simulation.md)).
:::

## Why two simulators

| | MuJoCo 3 | Gazebo Harmonic |
|---|---|---|
| Runs | Python process (`mujoco==3.17.0`) | Docker container with ROS 2 Jazzy |
| Strength | Fast, deterministic contact physics; easy to step thousands of times per second from Python | Simulates sensors (IMU, GPU LiDAR, camera) and runs the real ROS 2 nodes and controllers |
| Used for | Gait demo, PPO training and evaluation | End-to-end test of `gait_node` / `policy_node` with the same topics as the robot |
| Command | `make sim-walk`, `make rl-*` | `make sim-gazebo` |

Running a policy trained in MuJoCo through Gazebo is a cheap **sim-to-sim** check: if it only works in the simulator it was trained in, it has learned that simulator's quirks, and it will not survive the real robot either.

## The models, generated from CAD

`strido_cad.models` builds all simulation models from the verified CAD assembly, so the simulated robot has the real link lengths, masses and joint limits:

- 13 link meshes (`ros2/strido_description/meshes/`), decimated to 25 k faces each;
- masses from part volumes and densities, inertias from the meshes, cables by routed length: 3.07 kg in total (`ros2/strido_description/config/mass_report.yaml`);
- MJCF with 12 position actuators (`kp 25`, `kv 0.4`, torque limit ±3.432 N·m = SPT5435LV stall torque at 6 V), an IMU site with quaternion, gyro and accelerometer sensors, and foot sites;
- physics step 0.002 s (500 Hz) with the `implicitfast` integrator.

One simplification: the knee is modelled as a direct revolute joint on the calf. The four-bar linkage is solved in software (gait, firmware) and its limits are applied before commands reach the joint ([kinematics](kinematics-and-gaits.md)).

In Gazebo, the xacro with `sim:=true` adds `gz_ros2_control` with a `position` command interface per joint, an IMU (200 Hz), a GPU LiDAR (360 samples, 10 Hz, 0.05–12 m, Gaussian noise σ 0.01 m), a camera (640 × 360, 15 Hz) and a ground-truth odometry publisher (`/ground_truth/odom`, 50 Hz).

## MuJoCo: the gait walk

```bash
make sim-walk                                                     # 10 s trot at 0.15 m/s → build/sim/walk.mp4
uv run --locked python -m strido_sim.walk --seconds 6 --wz 0.6   # turn
uv run --locked mjpython -m strido_sim.walk --viewer             # interactive (macOS needs mjpython)
```

This runs `strido.gait`, the same trot the robot runs through ROS 2, at 100 Hz like the real command stream. It adds a heading hold using the simulator's yaw, which the robot does not have. Recorded result: 1.10 m in 10 s at 0.15 m/s, body height 0.174 m ([verification](../../verification.md)).

## Gazebo: the full ROS 2 stack

```bash
make sim-gazebo                               # build image, headless walk test, exit code = pass/fail
make sim-gazebo POLICY=models/policies/ppo-v1/policy.npz    # same test with policy_node
```

`walk_smoke` waits 6 s for the robot to stand, sends 0.15 m/s on `/cmd_vel` for 8 s and passes if the base moved ≥ 0.4 m forward (ground truth), stayed upright (|roll|, |pitch| < 0.5 rad, height > 0.10 m) and `/joint_states`, `/imu/data`, `/scan`, `/camera/image_raw` and `/ground_truth/odom` all published. Recorded: 0.98 m in 8 s with the gait node.

## Reinforcement learning in one paragraph

An **agent** (here: a neural network, the *policy* $\pi_\theta(a \mid s)$ with weights $\theta$) observes the state $s_t$, chooses an **action** $a_t$, and receives a **reward** $r_t$. Over millions of trials it adjusts itself to maximise the expected discounted return

$$
J(\theta) = \mathbb{E}_{\pi_\theta}\left[\sum_{t=0}^{\infty} \gamma^{t} r_t\right]
$$

where the discount $\gamma < 1$ makes near rewards count more than distant ones. With the repo's $\gamma = 0.99$ and 50 policy steps per second, rewards about $1/(1-\gamma) = 100$ steps (2 s) ahead still matter. **PPO** (Proximal Policy Optimisation) is a widely used algorithm for this: it collects a batch of experience with the current policy, then improves the policy in small, *clipped* steps so one bad batch cannot wreck it. It maximises

$$
L^\mathrm{CLIP}(\theta) = \mathbb{E}_t\left[\min\left(\rho_t(\theta)\,\hat A_t,\ \operatorname{clip}\left(\rho_t(\theta),\, 1-\epsilon,\, 1+\epsilon\right)\hat A_t\right)\right], \qquad \rho_t(\theta) = \frac{\pi_\theta(a_t \mid s_t)}{\pi_{\theta_\mathrm{old}}(a_t \mid s_t)}
$$

where $\hat A_t$ is the advantage (how much better the action was than the critic expected) and $\epsilon = 0.2$ here: once the new policy makes an action more than 20 % more or less likely than the old one did, the objective stops rewarding further change. The repo uses the PPO implementation of Stable-Baselines3 on the CPU. The full derivation is in [reinforcement learning](../theory/reinforcement-learning.md).

## The environment, as implemented

`StridoEnv` (`strido_sim/rl/env.py`) is a Gymnasium environment: "walk at the commanded velocity".

### Observations (23 numbers)

| Part | Size | Source on the robot |
|---|---|---|
| Angular velocity (gyro) | 3 | IMU (`/imu/data`) |
| Gravity direction in the body frame | 3 | IMU orientation quaternion |
| Command vx, vy, ωz | 3 | `/cmd_vel` |
| Previous action | 12 | the policy's own output |
| Gait clock sin, cos (0.4 s period) | 2 | a timer |

There are **no joint angles or velocities**. The SPT5435LV servos report nothing, so a policy that relied on joint feedback could not run on the robot (ADR-006 in [decisions](../../decisions.md)). The observation holds only what the robot can measure or knows.

### Actions (12 numbers)

Each action is in $[-1, 1]$. The joint target is $\mathbf{q}_\mathrm{target} = \mathbf{q}_\mathrm{stand} + 0.3\,\mathbf{a}$ (rad), then:

1. the firmware's 6 rad/s slew limit ($6\,\mathrm{rad/s} \times 0.02\,\mathrm{s} = 0.12\,\mathrm{rad}$ per policy step),
2. the joint and knee-crank clamp, exactly as the firmware does it.

Modelling these inside training means the policy learns with the same limits the robot will impose, instead of discovering them on hardware.

### Timing

Policy at 50 Hz (`CONTROL_DT = 0.02` s), physics at 500 Hz: $0.02\,\mathrm{s} / 0.002\,\mathrm{s} = 10$ physics steps per action. An episode lasts at most 1000 steps ($1000 \times 0.02\,\mathrm{s} = 20\,\mathrm{s}$).

### Commands

Each episode samples a command: 20 % of episodes stand still (zero command); the rest draw uniformly from vx −0.15…0.30 m/s, vy −0.10…0.10 m/s, ωz −0.6…0.6 rad/s. `policy_node` clips `/cmd_vel` to these ranges on the robot, because the policy has never seen anything outside them.

### Reward

Per step, scaled so perfect tracking gives at most $1.0 + 0.8 = 1.8$:

$$
\begin{aligned}
r = {} & 1.0\, \exp\!\left(-\lVert \mathbf{v}_{xy} - \mathbf{c}_{xy} \rVert^2 / 0.01\right) && \text{track linear velocity} \\
& + 0.8\, \exp\!\left(-(\omega_z - c_{\omega z})^2 / 0.05\right) && \text{track yaw rate} \\
& - 2.0\, v_z^2 && \text{no bouncing} \\
& - 0.05\, (\omega_x^2 + \omega_y^2) && \text{no rolling/pitching} \\
& - 0.01\, \lVert \mathbf{a}_t - \mathbf{a}_{t-1} \rVert^2 && \text{smooth actions} \\
& - 0.002 \sum_j \tau_j^2 && \text{save energy, spare the servos} \\
& - 2.0\, \max(0,\ 0.15\,\mathrm{m} - h) && \text{do not crouch below } 0.15\,\mathrm{m}
\end{aligned}
$$

Here $\mathbf{v}$ and $\boldsymbol{\omega}$ are the base's linear and angular velocity, $\mathbf{c}$ the command, $\mathbf{a}$ the action, $\tau_j$ the joint torques and $h$ the base height.

An episode ends with a −2 penalty if the base drops below 0.09 m or tilts beyond about 53°.

The exponential "tracking kernels" give a smooth reward that is 1 for perfect tracking and fades with error: with the width 0.01, a speed error of $0.1\,\mathrm{m/s}$ already drops the term to $e^{-1} \approx 0.37$. Penalties shape *how* the robot walks. The torque and action-rate terms matter more than they look: a hobby servo asked to jitter at 50 Hz heats up and wears its gears.

### Domain randomisation

The real robot will not match the model. Rather than hoping it does, training varies the model each episode so the policy learns to cope with a range:

| Randomised | Range |
|---|---|
| Servo stiffness (kp, and the matching bias) | × 0.85 … 1.15 |
| Base mass | × 0.90 … 1.15 |
| Contact friction, floor and feet together | × 0.6 … 1.2 |
| IMU noise | gyro σ 0.05 rad/s, gravity σ 0.02 |
| Initial joint angles | stand pose + σ 0.02 rad |

Floor and feet are scaled together because MuJoCo uses the larger friction of the two contacting geoms; scaling one alone would often change nothing.

## Training, exporting and evaluating

```bash
uv sync --locked --group rl                   # once: PyTorch, Stable-Baselines3, Gymnasium (opt-in, large)
make rl-smoke                                 # 20 k steps + evaluation: checks the pipeline in seconds
make rl-train                                 # 20 M steps, 8 parallel envs, CPU → build/rl/ppo-v1/
make rl-eval                                  # evaluate models/policies/ppo-v1/policy.npz with a video
uv run --locked --group rl python -m strido_sim.rl.evaluate build/rl/<run>/policy.npz --vx 0.2 --video build/rl/eval.mp4
```

Key PPO settings in `train.py`: 1024 steps per env per update, batch 2048, 5 epochs, learning rate $3 \times 10^{-4}$, $\gamma = 0.99$, GAE $\lambda = 0.95$, clip $\epsilon = 0.2$; actor `[128, 128]`, critic `[256, 256]`; observations and rewards normalised (`VecNormalize`, clip 10). The recorded `ppo-v1` run took 1734 s on a CPU.

Training writes `policy.zip` (Stable-Baselines3), `vecnormalize.pkl`, `progress.csv` and **`policy.npz`**: the actor's weights, biases and the observation mean/variance as plain arrays. `strido.policy.MlpPolicy` re-implements the forward pass in a dozen lines of NumPy: normalise $\tilde{\mathbf{o}} = \operatorname{clip}\left((\mathbf{o} - \boldsymbol{\mu})/\sqrt{\boldsymbol{\sigma}^2 + 10^{-8}},\ -10,\ 10\right)$, then $\mathbf{h}_1 = \tanh(\mathbf{W}_1 \tilde{\mathbf{o}} + \mathbf{b}_1)$, $\mathbf{h}_2 = \tanh(\mathbf{W}_2 \mathbf{h}_1 + \mathbf{b}_2)$, $\mathbf{a} = \operatorname{clip}(\mathbf{W}_3 \mathbf{h}_2 + \mathbf{b}_3,\ -1,\ 1)$. The same code runs in `evaluate.py` and in `policy_node`, so what is evaluated is bit-for-bit the function the robot runs, and the Pi needs no PyTorch.

### What ppo-v1 achieves

| Test | Result |
|---|---|
| MuJoCo, vx 0.2 m/s command (current limits) | 0.215 m/s mean, 2.15 m in 10 s, upright |
| MuJoCo, v0.1 sweep | vx 0.15 → 0.152 m/s; 0 → stands; −0.1 → −0.068 m/s; vy 0.1 → 0.023 m/s (weak); ωz 0.5 → 232° in 10 s |
| Gazebo through `policy_node` (sim-to-sim) | 0.82 m in 8 s at 0.15 m/s, upright |

Lateral and reverse tracking are weak: expected from a policy without joint feedback (ADR-006).

## The sim-to-real gap

Everything above is simulation. Nothing has yet run on a physical Strido. The known gaps:

- **Servo response.** kp 25 / kv 0.4 and zero latency are estimates; real hobby servos have dead band, backlash, gear compliance and a voltage-dependent speed.
- **Battery sag.** Servo speed and torque drop with pack voltage; the model assumes 6 V.
- **IMU.** Training reads a perfect quaternion plus Gaussian noise; the robot's comes from a Mahony filter with its own lag and bias.
- **Contacts.** Printed feet on a real floor, not a uniform plane with randomised friction.
- **Unmodelled mechanics.** The knee linkage is a direct joint in simulation; print tolerances and flex are not modelled.

The repo's procedure for a first hardware run: evaluate in MuJoCo and Gazebo, start with the robot on a stand, keep `/strido/estop` at hand, and expect to retrain with measured servo response (kp/kv, latency) once the robot exists.

```bash
ros2 launch strido_bringup robot.launch.py use_policy:=true policy:=/path/policy.npz
```

::: warning
A learned policy can command fast, large motions the scripted gait never would. The firmware's slew limit, joint clamps and watchdog still apply, but they cannot stop a leg hitting your hand. Test on a stand first ([safety](../making/safety.md)).
:::

## Check yourself

1. Why does the policy observe no joint angles?
2. What two firmware behaviours are reproduced inside `env.step()`, and why?
3. Why are floor and foot friction randomised together?
4. Why is `policy.npz` exported instead of running the Stable-Baselines3 model on the Pi?
5. What does running the MuJoCo-trained policy in Gazebo tell you?

<details>
<summary>Answers</summary>

1. The SPT5435LV servos have no position feedback; a policy must use only what the real robot measures (IMU, command, its own previous action, a clock).
2. The 6 rad/s slew limit and the joint/knee-crank clamp, so the policy trains under the same constraints the robot imposes.
3. MuJoCo uses the larger friction of the two contacting geoms; scaling only one would often have no effect.
4. The robot would need PyTorch; the NumPy runtime is small, and the same code is used in evaluation, so the deployed function is exactly the evaluated one.
5. Whether the policy depends on MuJoCo-specific quirks: a sim-to-sim gap is a warning sign for the sim-to-real gap.

</details>

## Further reading

- [MuJoCo documentation](https://mujoco.readthedocs.io/en/stable/overview.html)
- [Gazebo Harmonic documentation](https://gazebosim.org/docs/harmonic/getstarted/)
- [Stable-Baselines3 PPO](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html)
- [Schulman et al., Proximal Policy Optimization Algorithms (2017)](https://arxiv.org/abs/1707.06347)
- [Tobin et al., Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World (2017)](https://arxiv.org/abs/1703.06907)
- Theory: [Reinforcement learning](../theory/reinforcement-learning.md), [Legged locomotion](../theory/legged-locomotion.md)
