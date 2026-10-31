"""Start a detached, local camera preview; never replaces an active server.

Use the returned PID for a deliberate SIGTERM stop. PID/log files are created
exclusively, preserving any prior run. This does not register an init service.
"""
import datetime
from pathlib import Path
import subprocess
import sys


def main():
    package = Path(__file__).resolve().parent
    server = package / 'preview_server.py'
    capture = package / 'capture_camera0'
    if not server.is_file() or not capture.is_file():
        raise RuntimeError('camera package incomplete')
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            argv = (process / 'cmdline').read_bytes().split(b'\0')
        except OSError:
            continue
        if any(value == b'preview_server.py' or value.endswith(b'/preview_server.py') for value in argv):
            raise RuntimeError('a preview server is already running')
    log_dir = Path('/var/lib/amazinghand/log')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    pid_file = log_dir / ('camera0-preview-server-' + stamp + '.pid')
    log_file = log_dir / ('camera0-preview-server-' + stamp + '.txt')
    with pid_file.open('x') as pid_output, log_file.open('xb') as log:
        proc = subprocess.Popen([sys.executable, str(server), '--capture', str(capture)],
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True, close_fds=True)
        pid_output.write(str(proc.pid) + '\n')
    print('PREVIEW_PID', proc.pid)
    print('PREVIEW_PID_FILE', pid_file)
    print('PREVIEW_SERVER_LOG', log_file)
    print('PREVIEW_URL http://127.0.0.1:9000/')


if __name__ == '__main__':
    main()
