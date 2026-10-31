"""On-board bench fault injection for an owned preview/capture pair.

Stops/resumes then kills only the uniquely identified capture child. It verifies
stale/error HTTP responses and driver cleanup, and restarts capture afterwards.
Run with a live preview server; never use against another deployment profile.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

URL = 'http://127.0.0.1:9000'
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def status():
    return json.loads(OPENER.open(URL + '/status.json', timeout=5).read())


def post(path, data=None):
    request = urllib.request.Request(URL + '/' + path, json.dumps(data or {}).encode(),
                                     {'Content-Type': 'application/json'})
    return json.loads(OPENER.open(request, timeout=5).read())


def wait_live():
    begin = time.monotonic()
    while time.monotonic() - begin < 35:
        value = status()
        if value['state'] == 'LIVE':
            return value
        if value['state'] == 'ERROR':
            raise AssertionError(value)
        time.sleep(.1)
    raise AssertionError('preview did not become live')


def frame_rejected():
    for path in ('/frame.jpg', '/stream.mjpg'):
        try:
            OPENER.open(URL + path, timeout=5)
        except urllib.error.HTTPError as error:
            assert error.code == 503
        else:
            raise AssertionError('stale frame was served: ' + path)


def owned_child():
    candidates = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / 'cmdline').read_bytes().split(b'\0')
            if not argv[0].endswith(b'/capture_camera0'):
                continue
            parent = int((entry / 'status').read_text().split('PPid:')[1].split()[0])
            parent_argv = (Path('/proc') / str(parent) / 'cmdline').read_bytes().split(b'\0')
            if not any(value.endswith(b'/preview_server.py') or value == b'preview_server.py' for value in parent_argv):
                continue
            if not any(os.readlink(str(fd)) == '/dev/ah_camera0' for fd in (entry / 'fd').iterdir()):
                continue
            candidates.append(int(entry.name))
        except (OSError, ValueError, IndexError):
            continue
    assert len(candidates) == 1, candidates
    return candidates[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('/var/lib/amazinghand/log/camera0-preview-fault-validation-20261010.json'))
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('test output already exists')
    result = {}
    wait_live()
    hashes = []
    sequences = []
    for _ in range(12):
        sequences.append(status()['sequence'])
        hashes.append(hashlib.sha256(OPENER.open(URL + '/frame.jpg', timeout=5).read()).hexdigest())
        time.sleep(.25)
    assert len(set(hashes)) > 8 and sequences[-1] > sequences[0]
    result['different_jpegs'] = len(set(hashes))
    pid = owned_child()
    stream = OPENER.open(URL + '/stream.mjpg', timeout=5)
    assert stream.headers.get_content_type() == 'multipart/x-mixed-replace'
    assert stream.readline().strip() == b'--frame'
    os.kill(pid, signal.SIGSTOP)
    try:
        time.sleep(1.2)
        assert status()['state'] == 'STALE'
        frame_rejected()
        remainder = stream.read()
        stream.close()
        assert remainder and len(remainder) < 1000000
        result['existing_stream_closes_on_stale'] = True
        result['sigstop_stale_503'] = True
    finally:
        os.kill(pid, signal.SIGCONT)
    wait_live()
    result['sigcont_live'] = True
    os.kill(pid, signal.SIGKILL)
    for _ in range(30):
        if status()['state'] == 'ERROR':
            break
        time.sleep(.1)
    assert status()['state'] == 'ERROR'
    frame_rejected()
    subprocess.run([sys.executable, str(Path(__file__).with_name('test_device.py')), 'idle'], check=True)
    result['sigkill_error_503_and_dma_halt'] = True
    try:
        post('focus', {'position': 1024})
    except urllib.error.HTTPError as error:
        assert error.code == 400
        result['invalid_focus_rejected'] = True
    else:
        raise AssertionError('invalid focus accepted')
    post('start')
    wait_live()
    result['restart_live'] = True
    post('stop')
    assert status()['state'] == 'STOPPED'
    frame_rejected()
    result['stop_503'] = True
    post('start')
    wait_live()
    result['final_live'] = True
    destination = args.output
    with destination.open('x') as output:
        json.dump(result, output, indent=2)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
