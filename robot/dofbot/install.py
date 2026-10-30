"""Install the frozen demo into its supported VM without running hardware code."""
from contextlib import contextmanager
from pathlib import Path
import argparse
import ast
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT.parents[1]/'deliverables/dofbot_demo_20261029/payload'
HOME = Path('/home/yahboom')
DESTINATION = HOME/'codex_voice_sorting_20261029'
APP_FILES = (
    'standalone_runtime.py', 'standalone_voice.py', 'preview_publisher.py',
    'dashboard.py', 'dashboard_model.py', 'dashboard_launcher.py',
    'launch_controller.py', 'ensure_kinematics.py', 'voice_bridge.py',
    'start.sh', 'run_runtime.sh', 'dashboard-icon.svg',
)
PAYLOAD_FILES = APP_FILES + ('deployment_manifest.json', 'external_dependencies.json', 'README.md')


class InstallError(RuntimeError):
    pass


def verify_source(source=DEFAULT_SOURCE):
    source = Path(source)
    manifest = json.loads((source/'deployment_manifest.json').read_text(encoding='utf-8'))
    if set(manifest.get('files', {})) != set(APP_FILES):
        raise InstallError('源码清单与安装文件列表不一致。')
    for name in APP_FILES:
        data = (source/name).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest['files'][name]:
            raise InstallError('源码校验失败：'+name)
        if name.endswith('.py'):
            ast.parse(data, filename=name)
    for name in PAYLOAD_FILES:
        if not (source/name).is_file():
            raise InstallError('安装文件缺失：'+name)
    return manifest


def active_processes(destination, proc=Path('/proc')):
    destination, proc = Path(destination).resolve(), Path(proc)
    scripts = {str(destination/name) for name in (
        'standalone_runtime.py', 'run_runtime.sh', 'launch_controller.py', 'dashboard.py')}
    found = []
    if not proc.is_dir():
        return found
    for directory in proc.iterdir():
        if not directory.name.isdigit():
            continue
        try:
            args = {part.decode() for part in (directory/'cmdline').read_bytes().split(b'\0') if part}
            if args & scripts:
                found.append(int(directory.name))
        except (OSError, UnicodeError):
            continue
    return found


def check_environment(source=DEFAULT_SOURCE):
    """Only reads dependency files and device links; never opens a device."""
    if sys.platform != 'linux' or Path.home() != HOME or os.getuid() == 0:
        raise InstallError('正式安装请在配套 Ubuntu 虚拟机中以普通 yahboom 用户运行，不要 sudo。')
    if sys.version_info[:2] != (3, 10):
        raise InstallError('请使用配套虚拟机的 /usr/bin/python3（Python 3.10）执行安装。')
    release = Path('/etc/os-release').read_text()
    if 'VERSION_ID="22.04"' not in release:
        raise InstallError('此定稿版仅验证了 Ubuntu 22.04 配套虚拟机。')
    dependencies = json.loads((Path(source)/'external_dependencies.json').read_text(encoding='utf-8'))
    missing, changed = [], []
    for entry in dependencies['files']:
        path = Path(entry['path'])
        if not path.is_file():
            missing.append(str(path))
        elif entry.get('sha256') and hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            changed.append(str(path))
    for name in ('bash', 'fuser', 'pactl', 'mpg123'):
        if shutil.which(name) is None:
            missing.append('command: '+name)
    # Import availability is checked without importing any device-facing module.
    import importlib.util
    for name in ('serial', 'cv2', 'PyQt5'):
        if importlib.util.find_spec(name) is None:
            missing.append('Python module: '+name)
    if missing or changed:
        raise InstallError('外部依赖不满足。缺失：'+', '.join(missing)+'；版本不匹配：'+', '.join(changed))
    warnings = ['启动前连接设备：'+path for path in dependencies['devices'] if not Path(path).exists()]
    arm, voice = Path('/dev/myserial'), Path('/dev/myspeech')
    if arm.exists() and voice.exists() and arm.resolve() == voice.resolve():
        raise InstallError('机械臂与语音模块设备别名指向同一设备。')
    return warnings


@contextmanager
def exclusive_install(destination, staging):
    if staging:
        yield
        return
    import fcntl
    # This is the runtime's existing lock, so a concurrent start cannot enter
    # hardware initialization while the installer replaces individual files.
    handles = []
    try:
        paths = [Path('/tmp/dofbot-standalone-voice.lock')]
        launcher_lock = destination/'records/launcher.lock'
        if launcher_lock.parent.exists():
            paths.append(launcher_lock)
        for path in paths:
            handle = path.open('a')
            handles.append(handle)
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise InstallError('程序或启动入口正在运行，未覆盖安装。先完成本轮，再停止程序并关闭展示窗口。') from None
        yield
    finally:
        for handle in reversed(handles):
            handle.close()


def atomic_write(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.dofbot-install-', dir=str(path.parent), delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def payload(source, destination, home, desktop):
    planned = {}
    for name in PAYLOAD_FILES:
        planned[destination/name] = ((source/name).read_bytes(), 0o700 if name.endswith(('.py', '.sh')) else 0o600)
    for label, action in [('启动垃圾分拣', 'start'), ('停止垃圾分拣', 'stop')]:
        script = home/(label+'.sh')
        body = ('#!/usr/bin/env bash\nexport PYTHONIOENCODING=utf-8\n/bin/bash '+
                shlex.quote(str(destination/'start.sh'))+' "${1:-'+action+'}"\nresult=$?\n'+
                'if [[ -t 0 && -t 1 ]]; then read -r -p "按回车关闭此窗口。" reply; fi\nexit "$result"\n')
        planned[script] = (body.encode('utf-8'), 0o700)
        # Desktop Entry Exec quoting differs from shell quoting.
        escaped = str(script).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
        title = label+' · 实时展示' if action == 'start' else label
        entry = ('[Desktop Entry]\nVersion=1.0\nType=Application\nName='+title+
                 '\nComment=每轮重新唤醒后执行一次垃圾分拣\nExec=/bin/bash "'+escaped+
                 '"\nIcon='+str(destination/'dashboard-icon.svg')+
                 '\nTerminal=true\nCategories=Utility;\nStartupNotify=false\n')
        planned[desktop/(label+'.desktop')] = (entry.encode('utf-8'), 0o700)
    return planned


def install(source=DEFAULT_SOURCE, *, staging_root=None, check_only=False, proc=Path('/proc')):
    source = Path(source).resolve()
    manifest = verify_source(source)
    staging = staging_root is not None
    if staging:
        stage = Path(staging_root).resolve()
        home = (stage/'home/yahboom').resolve()
        if home == HOME or not home.is_relative_to(stage):
            raise InstallError('隔离验证目录不能映射到正式用户目录或越出指定范围。')
        destination, desktop, warnings = home/DESTINATION.name, home/'Desktop', []
    else:
        home, destination = HOME, DESTINATION
        warnings = check_environment(source)
        result = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True, text=True, check=True)
        desktop = Path(result.stdout.strip())
        if not desktop.is_absolute() or not desktop.is_dir():
            raise InstallError('无法确定 Ubuntu 桌面目录。')
    owners = active_processes(destination, proc)
    if owners:
        raise InstallError('现有实例仍在运行（PID %s），未覆盖。停止语音程序并关闭展示窗口后再安装。' % owners)
    planned = payload(source, destination, home, desktop)
    for path in [*planned, destination/'installation.json']:
        # No existing symlink, directory or symlinked ancestor can be replaced.
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise InstallError('安装目标不是普通文件：'+str(path))
        if path.absolute() != path.resolve():
            raise InstallError('安装目标经过符号链接，拒绝覆盖：'+str(path))
    if check_only:
        return dict(state='checked', source=str(source), destination=str(destination),
                    warnings=warnings, files=len(planned))
    with exclusive_install(destination, staging):
        if active_processes(destination, proc):
            raise InstallError('检测到并发启动，未覆盖安装。')
        backup = destination/'installer-backups'/str(time.time_ns())
        backup.mkdir(parents=True, exist_ok=False)
        originals, applied = {}, []
        for index, path in enumerate(planned):
            if path.exists():
                stored = backup/('%02d-' % index+path.name)
                shutil.copy2(path, stored)
                originals[path] = (stored, path.stat().st_mode & 0o777)
        if (destination/'installation.json').is_file():
            shutil.copy2(destination/'installation.json', backup/'previous-installation.json')
        try:
            for path, (data, mode) in planned.items():
                atomic_write(path, data, mode)
                applied.append(path)
        except Exception:
            for path in reversed(applied):
                if path in originals:
                    stored, mode = originals[path]
                    atomic_write(path, stored.read_bytes(), mode)
                else:
                    path.unlink(missing_ok=True)
            raise
        report = dict(state='installed', source=str(source), installed_at=time.time(), destination=str(destination),
                      backup=str(backup), staging=staging, warnings=warnings,
                      files=[str(path) for path in planned], source_files=manifest['files'],
                      backup_files={str(path): str(stored) for path, (stored, _) in originals.items()},
                      started_runtime=False, opened_devices=False, changed_volume=False)
        if not staging and shutil.which('gio'):
            env = os.environ.copy()
            env.update(XDG_RUNTIME_DIR='/run/user/'+str(os.getuid()),
                       DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/'+str(os.getuid())+'/bus')
            report['desktop_trust'] = {}
            for label in ('启动垃圾分拣', '停止垃圾分拣'):
                entry = desktop/(label+'.desktop')
                try:
                    result = subprocess.run(['gio', 'set', str(entry), 'metadata::trusted', 'true'],
                                            env=env, capture_output=True, text=True, timeout=5)
                    report['desktop_trust'][label] = result.returncode == 0
                except (OSError, subprocess.SubprocessError):
                    report['desktop_trust'][label] = False
        atomic_write(destination/'installation.json', json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8'), 0o600)
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='安装定稿版文件；不会启动机械臂或修改当前音量')
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE,
                        help='安装源目录；默认使用仓库内的冻结演示payload，也可指定独立冻结检出的robot/dofbot目录')
    parser.add_argument('--check', action='store_true', help='只读检查，不写入文件')
    parser.add_argument('--staging-root', type=Path, help='在隔离目录演练安装，不检查/操作系统与硬件')
    args = parser.parse_args(argv)
    try:
        result = install(source=args.source, staging_root=args.staging_root, check_only=args.check)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result['state'] == 'installed':
            print('安装完成，未启动控制程序。正式使用：bash ~/启动垃圾分拣.sh')
    except (InstallError, OSError, ValueError, SyntaxError, subprocess.SubprocessError) as exc:
        print('安装未完成：'+str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
