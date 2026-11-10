# Simulation and learning

All models are generated from the CAD by `strido_cad.models` (`make models`):

| File | Use |
|---|---|
| `ros2/strido_description/urdf/strido.urdf.xacro` (+ `strido.urdf`) | ROS 2 / Gazebo Harmonic: `sim:=true` adds `gz_ros2_control`, IMU, GPU LiDAR, camera and a ground-truth odometry publisher |
| `ros2/strido_description/meshes/*.stl` | 13 link meshes (decimated, 25 k faces each) |
| `models/mujoco/strido.xml`, `scene.xml` | MuJoCo 3: position servos (kp 25, kv 0.4, ±3.43 N·m = SPT5435LV stall torque), IMU and foot sites |

Link masses and inertias come from the CAD (`ros2/strido_description/config/mass_report.yaml`, total 3.07 kg incl. the routed wiring).
The knee is modelled as a direct revolute joint on the calf; the linkage is solved in software (gait, firmware) and
its limits are applied before commands reach the joint.

## MuJoCo

```bash
make sim-walk                                                        # 10 s trot at 0.15 m/s -> build/sim/walk.mp4
uv run --locked python -m strido_sim.walk --seconds 6 --wz 0.6   # turn
uv run --locked mjpython -m strido_sim.walk --viewer             # interactive (macOS needs mjpython)
```

The walking demo runs `packages/strido-core/src/strido/gait.py`, the gait the robot runs through ROS 2, plus a heading hold that uses the simulator's yaw (the robot has no such loop).

## Gazebo Harmonic (ROS 2 Jazzy, Docker)

```bash
make sim-gazebo          # build image, headless walk test with pass/fail
docker compose -f docker/compose.yaml run --rm ros ros2 launch strido_bringup gazebo.launch.py   # GUI needs X11/Wayland forwarding
```

`POLICY=/path/policy.npz` runs the same test with `policy_node` (mount the file into the container, see `docker/ros2/sim_smoke.sh`). `walk_smoke` stands the robot up, commands 0.15 m/s for 8 s and checks ground-truth progress
(≥ 0.4 m), uprightness and that `/joint_states`, `/imu/data`, `/scan`, `/camera/image_raw` and
`/ground_truth/odom` are publishing.

## Reinforcement learning (MuJoCo + PPO)

`strido_sim.rl.env` (`packages/strido-sim`) is a Gymnasium velocity-tracking task designed for transfer to
hobby servos: the policy only observes what the robot can measure (IMU gyro and gravity, command,
its previous action, a gait clock) — no joint feedback, because the SPT5435LV has none. Actions are
joint offsets around the stand pose, clamped by the same joint and knee-crank limits as the firmware.
The firmware's 6 rad/s joint slew limit is applied in the environment (per 20 ms policy step; the firmware
ramps in 5 ms steps at the same speed), followed by the joint and knee-crank clamp. Domain randomisation: contact friction (floor and feet together,
since MuJoCo uses the larger of the two), servo stiffness, base mass, IMU noise. `policy_node` clips
`/cmd_vel` to the trained command ranges and publishes no `/odom` (use LiDAR odometry/SLAM).

```bash
make rl-smoke                                                        # 20 k steps + evaluation (pipeline check)
make rl-train                                                        # 20 M steps, 8 envs (CPU, ≈ 30 min)
uv run --locked python -m strido_sim.rl.evaluate build/rl/<run>/policy.npz --vx 0.2 --video build/rl/eval.mp4
```

Training writes `policy.npz` (plain arrays). `strido.policy.MlpPolicy` runs it with numpy, both in
`evaluate.py` and in the ROS 2 `policy_node`, so no PyTorch is needed on the Pi:

```bash
ros2 launch strido_bringup gazebo.launch.py use_policy:=true policy:=/path/policy.npz
ros2 launch strido_bringup robot.launch.py  use_policy:=true policy:=/path/policy.npz
```

Before running a learned policy on hardware: evaluate it in MuJoCo and Gazebo, start with the robot on
a stand, keep `/strido/estop` at hand, and expect to retrain with measured servo response (kp/kv,
latency) once the robot exists.

The upstream PyBullet (`upstream/yertle/learning/`) and Isaac Lab (`upstream/yertle/isaac_lab/`) pipelines
target the original Yertle URDF and are kept for reference.
