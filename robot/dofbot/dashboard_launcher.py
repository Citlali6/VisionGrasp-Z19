"""Open the read-only exhibition window in the logged-in Ubuntu session."""
from pathlib import Path
import json,os,subprocess,time,uuid

ROOT=Path(__file__).resolve().parent
SESSION_KEYS=('DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS')

def desktop_environment():
    env=os.environ.copy()
    # vmrun and ordinary terminals can have different session environments.
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():continue
        try:
            if directory.stat().st_uid!=os.getuid():continue
            command=(directory/'cmdline').read_bytes().split(b'\0')
            if not command or Path(command[0].decode()).name not in ('gnome-shell','gnome-session-binary'):continue
            source=dict(v.split('=',1) for v in (directory/'environ').read_bytes().decode().split('\0') if '=' in v)
            for key in SESSION_KEYS:
                if source.get(key):env[key]=source[key]
            if source.get('DISPLAY'):break
        except (OSError,ValueError,UnicodeError):continue
    uid=str(os.getuid())
    env.setdefault('DISPLAY',':0')
    env.setdefault('XDG_RUNTIME_DIR','/run/user/'+uid)
    env.setdefault('DBUS_SESSION_BUS_ADDRESS','unix:path=/run/user/'+uid+'/bus')
    env.update(QT_QPA_PLATFORM='xcb',PYTHONUNBUFFERED='1',PYTHONIOENCODING='utf-8')
    # Never inherit OpenCV's bundled Qt plugin directory from a ROS terminal.
    env.pop('QT_QPA_PLATFORM_PLUGIN_PATH',None)
    env.pop('QT_QPA_FONTDIR',None)
    return env

def valid_dashboard(root, requested_at, token):
    try:
        state=json.loads((root/'records/dashboard.json').read_text())
        cmd=[v.decode() for v in Path('/proc',str(int(state['pid'])),'cmdline').read_bytes().split(b'\0') if v]
        return (cmd[:3]==['/usr/bin/python3','-B',str(root/'dashboard.py')]
                and state.get('updated_at',0)>=requested_at and state.get('visible') is True
                and state.get('activation_ack')==token
                and not state.get('closed'))
    except (OSError,ValueError,KeyError):return False

def launch_dashboard(root=ROOT, report=print):
    root=Path(root).resolve()
    try:
        if not (root/'dashboard.py').is_file():raise RuntimeError('缺少 dashboard.py')
        requested_at=time.time()
        token=uuid.uuid4().hex
        with (root/'records/dashboard.log').open('ab',buffering=0) as log:
            process=subprocess.Popen(['/usr/bin/python3','-B',str(root/'dashboard.py'),'--activation-token',token],
                cwd=str(root),env=desktop_environment(),stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            if valid_dashboard(root,requested_at,token):
                report('展示窗口已打开。F11 切换全屏；关闭窗口只关闭显示，不会停止后台任务。')
                return True
            if process.poll() not in (None,0):break
            time.sleep(.2)
        raise RuntimeError('未确认窗口显示，请查看 records/dashboard.log，并确认已登录 Ubuntu 桌面')
    except (OSError,RuntimeError) as exc:
        report('展示窗口未就绪：'+str(exc)+'。再次运行启动命令可重试打开窗口。')
        return False

if __name__=='__main__':
    raise SystemExit(0 if launch_dashboard() else 1)
