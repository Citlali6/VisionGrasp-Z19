#!/usr/bin/env bash
set -e
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONIOENCODING=utf-8
exec /usr/bin/python3 -B "$task_dir/launch_controller.py" "${1:-start}"
