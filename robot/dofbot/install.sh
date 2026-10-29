#!/usr/bin/env bash
# Install files only. This entry never starts recognition or arm control.
set -e
installer_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec /usr/bin/python3 -B "$installer_dir/install.py" "$@"
