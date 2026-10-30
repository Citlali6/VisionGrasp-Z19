#!/usr/bin/env python3
"""Idempotent, no-motion launcher for the deployed standalone voice runtime."""
from contextlib import contextmanager
from pathlib import Path
import argparse
import datetime
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
CAMERA = Path('/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._USB_2.0_Camera-video-index0')
SINK = 'alsa_output.usb-C-Media_Electronics_Inc._USB_Audio_Device-00.analog-stereo'
READY_STATES = {'waiting_wake', 'waiting_start', 'preparing', 'recognizing', 'announcing', 'grasping'}


class LaunchError(RuntimeError):
    pass


def read_json(path):
    try:
        value = Path(path).read_text(encoding='utf-8')
        result = json.loads(value)
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


class Launcher:
    def __init__(self, root=ROOT, *, proc_root=Path('/proc'), clock=time.time,
                 sleep=time.sleep, report=print):
        self.root, self.proc = Path(root).resolve(), Path(proc_root)
        self.records = self.root/'records'
        self.clock, self.sleep, self.report = clock, sleep, report

    @contextmanager
    def locked(self):
        import fcntl
        self.records.mkdir(parents=True, exist_ok=True)
        with (self.records/'launcher.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise LaunchError('另一条启动或停止命令正在执行，请稍后重试。') from None
            yield

    def expected_command(self, command):
        script = str(self.root/'standalone_runtime.py')
        return command in ([ '/usr/bin/python3', '-B', script, '--execute'],
                           [ '/usr/bin/python3', script, '--execute'])

    def identity(self, pid):
        try:
            pid = int(pid)
            if pid <= 0: return None
            directory = self.proc/str(pid)
            command = [x.decode() for x in (directory/'cmdline').read_bytes().split(b'\0') if x]
            stat = (directory/'stat').read_text()
            fields = stat[stat.rfind(')')+2:].split()
            start_ticks = int(fields[19])
            btime = int(re.search(r'^btime (\d+)$', (self.proc/'stat').read_text(), re.M).group(1))
            hz = os.sysconf('SC_CLK_TCK') if hasattr(os, 'sysconf') else 100
            return dict(pid=pid, command=command, start_ticks=start_ticks,
                        start_epoch=btime+start_ticks/hz,
                        boot_id=(self.proc/'sys/kernel/random/boot_id').read_text().strip())
        except (OSError, ValueError, IndexError, AttributeError):
            return None

    def runtime_processes(self):
        found = []
        for directory in self.proc.iterdir():
            if directory.name.isdigit():
                identity = self.identity(directory.name)
                if identity and self.expected_command(identity['command']):
                    found.append(identity)
        return found

    def current(self):
        boot = read_json(self.records/'bootstrap.json')
        process = self.identity(boot.get('pid', 0))
        if not process or not self.expected_command(process['command']):
            return None
        started = boot.get('started_at')
        if not isinstance(started, (float, int)):
            return None
        # A recycled PID with the same command is not the previous session.
        if not process['start_epoch'] <= started <= process['start_epoch']+120:
            return None
        if started > self.clock()+1:
            return None
        manifest = read_json(self.records/'launcher.json')
        if manifest.get('pid') == process['pid']:
            if (manifest.get('start_ticks') != process['start_ticks']
                    or manifest.get('boot_id') != process['boot_id']
                    or started < manifest.get('requested_at', 0)):
                return None
        status = read_json(self.records/'status.json')
        try:
            if (self.records/'status.json').stat().st_mtime < started:
                status = {}
        except OSError:
            status = {}
        return dict(process=process, boot=boot, status=status)

    def starting_process(self):
        """A timed-out launch may still be in its recorded ROS setup shell."""
        manifest = read_json(self.records/'launcher.json')
        identity = self.identity(manifest.get('pid', 0))
        if (identity is not None
                and identity['command'] == ['/bin/bash', str(self.root/'run_runtime.sh')]
                and manifest.get('start_ticks') == identity['start_ticks']
                and manifest.get('boot_id') == identity['boot_id']):
            return identity
        return None

    def _describe(self, current):
        status = current['status']
        pid = current['process']['pid']
        if status.get('error') or status.get('state') == 'fault':
            raise LaunchError('程序仍在运行，但处于故障状态（PID %s）：%s。请先查看 records/status.json 和 runtime.log；修复后在空闲时执行 stop，再执行 start。' % (pid, status.get('error', '未知错误')))
        if status.get('state') not in READY_STATES or current['boot'].get('state') != 'ready_for_standalone_voice':
            raise LaunchError('程序已存在（PID %s），尚未确认就绪；不会重复启动。请稍后执行 status，查看 records/runtime.log。' % pid)
        if status.get('busy'):
            self.report('程序正在执行本轮任务（PID %s，阶段 %s），请等待本轮完成。' % (pid, status['state']))
        else:
            self.report('独立语音程序已就绪（PID %s），无需手机。先说“你好小亚”，再说“开始垃圾分拣”。' % pid)

    def status(self):
        current = self.current()
        if current:
            self._describe(current)
            status = current['status']
            if status.get('labelChinese'):
                self.report('最近识别：%s / %s；本次进程已调用抓取 %s 次。' %
                            (status['labelChinese'], status.get('categoryChinese', ''), status.get('grasp_calls', 0)))
            return current
        starting = self.starting_process()
        if starting:
            self.report('启动准备程序仍在运行（PID %s），正在等待 ROS/IK 等准备完成，尚未确认就绪；不会重复启动。请查看 records/runtime.log，稍后执行 status。' % starting['pid'])
            return dict(process=starting, starting=True)
        if self.runtime_processes():
            raise LaunchError('发现本程序进程，但启动记录与进程身份不匹配；不会启动或停止它，请检查 records/runtime.log。')
        self.report('独立语音程序未运行。执行 start 启动；旧 status.json 仅是历史记录。')
        return None

    def environment(self):
        env = os.environ.copy()
        uid = os.getuid()
        env.update(XDG_RUNTIME_DIR='/run/user/'+str(uid),
                   PULSE_SERVER='unix:/run/user/'+str(uid)+'/pulse/native',
                   PULSE_SINK=SINK, PYTHONUNBUFFERED='1')
        return env

    def preflight(self, allowed_pid=None):
        devices = [Path('/dev/myserial'), Path('/dev/myspeech'), CAMERA]
        missing = [str(p) for p in devices if not p.exists()]
        if missing:
            raise LaunchError('设备未接入虚拟机：'+', '.join(missing)+'。请在 VMware 中连接机械臂USB、语音USB和摄像头。')
        if devices[0].resolve() == devices[1].resolve():
            raise LaunchError('机械臂与语音串口指向同一设备，请检查 USB 透传和 udev 别名。')
        if not (self.root/'run_runtime.sh').is_file() or not (self.root/'standalone_runtime.py').is_file():
            raise LaunchError('启动文件不完整：缺少 run_runtime.sh 或 standalone_runtime.py。')
        for name in ('fuser', 'pactl', 'mpg123'):
            if shutil.which(name) is None:
                raise LaunchError('缺少命令：'+name)
        for device in devices:
            result = subprocess.run(['fuser', str(device)], capture_output=True, text=True, timeout=5)
            owners = {int(v) for v in result.stdout.split() if v.isdigit()}
            if result.returncode == 0 and owners and allowed_pid is not None and owners == {allowed_pid}:
                continue
            if result.returncode != 1:
                raise LaunchError('设备被其他程序占用或无法确认空闲：%s；PID %s。请先退出手机APP服务/Jupyter控制脚本，不会强行抢占。' % (device, sorted(owners)))
        env = self.environment()
        sinks = subprocess.run(['pactl', 'list', 'short', 'sinks'], env=env,
                               capture_output=True, text=True, timeout=5)
        if sinks.returncode or not any(len(line.split()) > 1 and line.split()[1] == SINK for line in sinks.stdout.splitlines()):
            raise LaunchError('找不到 C-Media USB 声卡或当前用户的 PulseAudio 会话。请登录 Ubuntu 桌面，并将 USB Audio Device 连接到虚拟机。')
        modules = subprocess.run(['mpg123', '--list-modules'], env=env,
                                 capture_output=True, text=True, timeout=5)
        if modules.returncode or not re.search(r'^pulse\s+output\b', modules.stdout+modules.stderr, re.M):
            raise LaunchError('mpg123 缺少 pulse 输出模块，不能保证分类播报；未启动机械臂程序。')
        self.report('检查通过：机械臂、语音模块、固定摄像头和 USB 声卡可用；检查未发送机械臂指令。')
        return env

    def check(self):
        current = self.current()
        self.preflight(current['process']['pid'] if current else None)
        if current:
            self._describe(current)

    def archive_session(self):
        names = {'bootstrap.json', 'status.json', 'status.tmp', 'arm-tx.jsonl', 'runtime.log', 'launcher.json'}
        files = [p for p in self.records.iterdir() if p.name in names or
                 p.name.startswith('cycle-') and p.suffix == '.jpg']
        if not files:
            return
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+str(time.time_ns())
        destination = self.records/'archive'/stamp
        destination.mkdir(parents=True, exist_ok=False)
        for path in files:
            path.rename(destination/path.name)
        self.report('上一轮记录已保存到 '+str(destination))

    def _write_manifest(self, data):
        temporary = self.records/'launcher.tmp'
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.records/'launcher.json')

    def wait_ready(self, process, manifest, timeout=60):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise LaunchError('启动进程已退出（退出码 %s），请查看 records/runtime.log。' % process.returncode)
            identity = self.identity(process.pid)
            if identity and (identity['start_ticks'] != manifest['start_ticks'] or identity['boot_id'] != manifest['boot_id']):
                raise LaunchError('启动进程身份变化，拒绝把其他进程认作本程序。')
            boot, status = read_json(self.records/'bootstrap.json'), read_json(self.records/'status.json')
            matching = (identity is not None and self.expected_command(identity['command'])
                        and boot.get('pid') == process.pid
                        and isinstance(boot.get('started_at'), (int, float))
                        and boot['started_at'] >= manifest['requested_at'])
            if matching:
                if boot.get('exit') or status.get('error') or status.get('state') == 'fault':
                    raise LaunchError('启动失败：'+str(status.get('error') or boot.get('exit') or '未知错误'))
                events = status.get('events', [])
                fresh = {e.get('event') for e in events if isinstance(e, dict)
                         and isinstance(e.get('at'), (int, float)) and e['at'] >= boot['started_at']}
                if (boot.get('state') == 'ready_for_standalone_voice'
                        and status.get('state') in READY_STATES
                        and {'ready', 'serial_open'} <= fresh):
                    manifest['ready_at'] = self.clock()
                    manifest['bootstrap_started_at'] = boot['started_at']
                    self._write_manifest(manifest)
                    current = dict(process=identity, boot=boot, status=status)
                    self._describe(current)
                    return current
            self.sleep(.25)
        raise LaunchError('60秒内未确认新进程就绪。没有再次启动或强制杀进程；请执行 status 并查看 records/runtime.log。')

    def start(self):
        with self.locked():
            current = self.current()
            if current:
                self._describe(current)
                return current
            if self.starting_process():
                raise LaunchError('已有启动准备程序仍在运行（可能是上次等待超时后继续准备），不会重复启动。请查看 records/runtime.log，稍后执行 status。')
            if self.runtime_processes():
                raise LaunchError('已有独立程序正在启动或身份记录不匹配；不会重复启动，请查看日志。')
            env = self.preflight()
            self.archive_session()
            requested_at = self.clock()
            with (self.records/'runtime.log').open('ab', buffering=0) as log:
                process = subprocess.Popen(['/bin/bash', str(self.root/'run_runtime.sh')],
                    cwd=str(self.root), env=env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            identity = self.identity(process.pid)
            if identity is None:
                raise LaunchError('启动进程立即退出或无法读取身份，请查看 records/runtime.log。')
            manifest = dict(pid=process.pid, requested_at=requested_at,
                            start_ticks=identity['start_ticks'], boot_id=identity['boot_id'])
            self._write_manifest(manifest)
            return self.wait_ready(process, manifest)

    def _same_process(self, expected):
        current = self.identity(expected['pid'])
        return (current is not None and self.expected_command(current['command'])
                and current['start_ticks'] == expected['start_ticks']
                and current['boot_id'] == expected['boot_id'])

    def _signal_owned(self, expected):
        if hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'):
            descriptor = os.pidfd_open(expected['pid'])
            try:
                if not self._same_process(expected):
                    raise LaunchError('PID身份已变化，未发送停止信号。')
                signal.pidfd_send_signal(descriptor, signal.SIGTERM)
            finally:
                os.close(descriptor)
        else:
            if not self._same_process(expected):
                raise LaunchError('PID身份已变化，未发送停止信号。')
            os.kill(expected['pid'], signal.SIGTERM)

    def stop(self):
        with self.locked():
            current = self.current()
            if not current:
                if self.starting_process():
                    raise LaunchError('程序仍在启动准备阶段，尚未取得可停止的运行状态；未发送停止信号，请稍后执行 status。')
                if self.runtime_processes():
                    raise LaunchError('进程身份记录不匹配，未发送停止信号。')
                self.report('程序未运行，无需停止。')
                return
            status = current['status']
            if status.get('busy') is not False:
                raise LaunchError('程序正在执行本轮任务或状态尚未确认。请等本轮完成后再执行 stop；没有发送停止信号。')
            self._signal_owned(current['process'])
            deadline = time.monotonic()+10
            while time.monotonic() < deadline:
                if not self._same_process(current['process']):
                    self.report('独立语音程序已停止，未强制中断动作。')
                    return
                self.sleep(.2)
            raise LaunchError('已发送正常退出请求，进程仍未退出；没有使用强制终止。请查看日志，稍后执行 status。')


def main(argv=None):
    parser = argparse.ArgumentParser(description='独立语音垃圾分拣：启动、状态、停止和设备检查')
    parser.add_argument('command', choices=('start', 'status', 'stop', 'check'), nargs='?', default='start')
    args = parser.parse_args(argv)
    try:
        getattr(Launcher(), args.command)()
    except (LaunchError, OSError, subprocess.SubprocessError) as exc:
        print('未完成：'+str(exc), file=sys.stderr)
        return 1
    finally:
        if args.command == 'start':
            from dashboard_launcher import launch_dashboard
            launch_dashboard()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
