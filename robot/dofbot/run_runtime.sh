#!/usr/bin/env bash
# Internal entry. Use start.sh for preflight and duplicate-start protection.
set -e
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$task_dir"
source /opt/ros/humble/setup.bash
source /home/yahboom/dofbot_ws/install/setup.bash
source /home/yahboom/LargeModel_ws/install/setup.bash
# Match the environment in which the current physical demo was verified.
export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export PULSE_SERVER="unix:${XDG_RUNTIME_DIR}/pulse/native"
export PYTHONUNBUFFERED=1
export PYTHONIOENCODING=utf-8
/usr/bin/python3 -B "$task_dir/ensure_kinematics.py"
exec /usr/bin/python3 -B "$task_dir/standalone_runtime.py" --execute
