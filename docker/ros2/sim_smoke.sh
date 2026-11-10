#!/bin/bash
# Headless Gazebo smoke test: launch the simulation, stand up, walk 8 s at 0.15 m/s,
# check ground-truth progress and sensor topics. Exit code from walk_smoke.
set -u
# POLICY=/path/policy.npz (inside the container) tests the learned controller instead of the gait
EXTRA=()
if [ -n "${POLICY:-}" ]; then EXTRA=(use_policy:=true "policy:=${POLICY}"); fi
setsid ros2 launch strido_bringup gazebo.launch.py headless:=true "${EXTRA[@]}" > /tmp/gazebo.log 2>&1 &
LAUNCH_PID=$!
ros2 run strido_control walk_smoke --ros-args -p use_sim_time:=true
STATUS=$?
# stop the whole launch process group (gz server, bridge, controllers); escalate if it hangs
kill -INT -- "-$LAUNCH_PID" 2>/dev/null
for _ in $(seq 1 20); do
  kill -0 "$LAUNCH_PID" 2>/dev/null || break
  sleep 0.5
done
kill -KILL -- "-$LAUNCH_PID" 2>/dev/null
pkill -KILL -f "gz sim" 2>/dev/null
if [ "$STATUS" -ne 0 ]; then
  echo "--- gazebo.log (tail) ---"
  tail -n 60 /tmp/gazebo.log
fi
exit "$STATUS"
