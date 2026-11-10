# Configuration

> **Status:** every environment key the code reads. Defaults live in the committed `.env.example`; secrets: none.

| Key | Default | Read by | Meaning |
|---|---|---|---|
| `ROS_DOMAIN_ID` | `42` | `docker/compose.yaml` | ROS 2 domain of the robot and simulation containers |
| `STRIDO_BLENDER` | *(empty)* | `strido_publish.scene` | Blender executable for renders; empty = `blender` on PATH, else the macOS app bundle |
| `STRIDO_PRUSASLICER` | *(empty)* | `strido_verify.printability` | PrusaSlicer executable for the printability gate; empty = `prusa-slicer` on PATH, else the macOS app bundle |
| `STRIDO_REPO_ROOT` | *(empty)* | `strido.workspace` | Repository root for the tooling when running outside the checkout |
| `STRIDO_SERIAL_PORT` | `/dev/strido_mcu` | `strido-cli`, `strido_ntx.plugin` | Serial device of the XIAO ESP32-S3 (udev symlink from `ros2/strido_bringup/config/99-strido.rules`) |

The ROS 2 launch files take the same values as launch arguments (`mcu_port`, `use_policy`, `policy`, `camera`). Makefile variables: `NTX_HARNESS` (path of the NT-X checkout for `make ntx-smoke`, default `../../ntx-harness`), `POLICY` (policy file for `make sim-gazebo`).
