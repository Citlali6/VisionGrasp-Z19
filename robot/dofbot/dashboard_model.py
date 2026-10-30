"""Read-only presentation model. No device access or inferred physical success."""
from pathlib import Path
import json
import math
import os
import time

CATEGORIES = {
    '01': ('可回收垃圾', '#59A7FF', 'RECYCLE'),
    '02': ('其他垃圾', '#A3ADBD', 'OTHER'),
    '03': ('厨余垃圾', '#3FD6A0', 'KITCHEN'),
    '04': ('有害垃圾', '#FF7A89', 'HAZARDOUS'),
}
PHASES = {'grasping': '抓取阶段', 'transferring': '转运阶段',
          'releasing': '释放阶段', 'returning': '返回阶段'}
AUDIO_TEXT = {
    94: '这是易拉罐，属于可回收垃圾', 95: '这是旧书包，属于可回收垃圾',
    96: '这是报纸，属于可回收垃圾', 97: '这是书本，属于可回收垃圾',
    98: '这是注射器，属于有毒垃圾', 99: '这是废旧电池，属于有毒垃圾',
    100: '这是过期化妆品，属于有毒垃圾', 101: '这是过期药品，属于有毒垃圾',
    102: '这是鱼骨，属于湿垃圾', 103: '这是西瓜皮，属于湿垃圾',
    104: '这是苹果核，属于湿垃圾', 105: '这是鸡蛋壳，属于湿垃圾',
    106: '这是一次性筷子，属于干垃圾', 107: '这是烟蒂，属于干垃圾',
    108: '这是桃核，属于干垃圾', 109: '这是卫生纸，属于干垃圾',
}


def number(value, default=0.):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def read_json(path):
    try:
        path = Path(path)
        if path.stat().st_size > 2_000_000:
            return {}
        result = json.loads(path.read_text(encoding='utf-8'))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def runtime_alive(root, boot, proc=Path('/proc')):
    """Bind the evidence to the exact live runtime, including PID reuse checks."""
    try:
        pid = int(boot['pid'])
        if pid <= 0:
            return False
        directory = Path(proc)/str(pid)
        command = [part.decode() for part in (directory/'cmdline').read_bytes().split(b'\0') if part]
        script = str(Path(root).resolve()/'standalone_runtime.py')
        if command not in (['/usr/bin/python3', '-B', script, '--execute'],
                           ['/usr/bin/python3', script, '--execute']):
            return False
        stat = (directory/'stat').read_text()
        fields = stat[stat.rfind(')')+2:].split()
        if fields[0] in ('Z', 'X'):
            return False
        epoch = next(int(line.split()[1]) for line in (Path(proc)/'stat').read_text().splitlines()
                     if line.startswith('btime '))
        hz = os.sysconf('SC_CLK_TCK') if hasattr(os, 'sysconf') else 100
        actual_start = epoch + int(fields[19])/hz
        return actual_start <= number(boot.get('started_at')) <= actual_start+120
    except (OSError, ValueError, TypeError, KeyError, IndexError, StopIteration):
        return False


def timeline(events):
    rows = []
    language = 'cn'
    for event in events:
        kind = event.get('event')
        text, tone = None, 'muted'
        if kind == 'wake_received':
            language = event.get('language', 'cn')
            text, tone = '唤醒词已识别', 'accent'
        elif kind == 'wake_audio_completed':
            text = '回应“在的”已播放' if language == 'cn' else '唤醒回应已播放（英文）'
        elif kind == 'start_accepted':
            text, tone = '启动口令已识别 · '+('开始分拣' if event.get('command') == 92 else '开始垃圾分拣'), 'accent'
        elif kind == 'announcing':
            script = AUDIO_TEXT.get(event.get('audio_id')) if language == 'cn' else None
            text = ('播报文案 · '+script) if script else ('播报摘要 · '+str(event.get('labelChinese', ''))+' · '+str(event.get('categoryChinese', '')))
            tone = 'accent'
        elif kind == 'classification_audio_completed':
            text = '分类语音播放完成'
        elif kind == 'grasping':
            text, tone = '开始执行抓取与投放流程', 'accent'
        elif kind == 'cycle_finished':
            result = event.get('result')
            text, tone = ('本轮执行结束 · 等待重新唤醒', 'accent') if result == 'official_grasp_callback_completed' else ('本轮已结束 · '+{'no_stable_target_timeout': '未找到稳定目标', 'failed': '运行异常', 'cancelled': '已取消', 'dry_run_completed': '仅识别验证'}.get(result, '等待下一轮'), 'muted')
        elif kind in ('fault', 'recognition_timeout', 'cycle_cancelled'):
            text, tone = {'fault': '运行异常 · 请检查设备与运行日志', 'recognition_timeout': '识别超时 · 本轮未执行抓取', 'cycle_cancelled': '本轮任务已取消'}[kind], 'error'
        elif kind == 'input_rejected' and event.get('reason') == 'wake_required':
            text = '请先重新唤醒，再说启动口令'
        if text:
            rows.append({'at': number(event.get('at')), 'text': text, 'tone': tone})
    return rows[-40:]


def load_view(root, now=None, proc=Path('/proc'), runtime_check=runtime_alive):
    root = Path(root).resolve()
    now = time.time() if now is None else now
    records = root/'records'
    boot = read_json(records/'bootstrap.json')
    status = read_json(records/'status.json')
    alive = runtime_check(root, boot, proc)
    started = number(boot.get('started_at'))
    try:
        status_fresh = (records/'status.json').stat().st_mtime >= started
    except OSError:
        status_fresh = False
    online = bool(alive and status_fresh and status)
    if not online:
        status = {}
    events = [e for e in status.get('events', []) if isinstance(e, dict)
              and started <= number(e.get('at')) <= now+1]
    preview = Path(boot.get('preview_dir') or '/run/user/%s/dofbot-voice-preview' % (os.getuid() if hasattr(os, 'getuid') else 1000))
    live = read_json(preview/'live.json')
    matches = (online and live.get('pid') == boot.get('pid')
               and abs(number(live.get('session_started_at'))-started) < .01)
    fresh_frame = (matches and 0 <= now-number(live.get('frame_at')) < 2
                   and 0 <= now-number(live.get('updated_at')) < 2.5)
    camera_live = bool(fresh_frame and live.get('active') is True and live.get('camera_live') is True
                       and not live.get('camera_error') and not live.get('preview_error')
                       and live.get('image_sequence') is not None
                       and live.get('image_sequence') == live.get('sequence')
                       and (preview/'latest.jpg').is_file())
    state = status.get('state', 'offline')
    # Recompute wake expiry: status.json is event-driven, not a live clock.
    wake_at = None
    for event in events:
        if event.get('event') == 'wake_received':
            wake_at = number(event.get('at'))
        elif event.get('event') in ('start_accepted', 'cycle_finished', 'fault', 'stop_requested'):
            wake_at = None
    awake = bool(online and wake_at is not None and 0 <= now-wake_at <= 20)
    if state == 'waiting_start' and not awake:
        state = 'waiting_wake'
    cycle_events = events
    for index in range(len(events)-1, -1, -1):
        if events[index].get('event') == 'start_accepted':
            cycle_events = events[index:]
            break
    confirmed = any(e.get('event') in ('recognition_image', 'announcing') for e in cycle_events)
    confirmed = bool(confirmed and status.get('labelChinese') and status.get('category') in CATEGORIES)
    label = str(status['labelChinese']) if confirmed else '等待识别'
    category = str(status.get('category')) if confirmed else None
    arm = live.get('arm', {}) if matches else {}
    arm = arm if isinstance(arm, dict) else {}
    phase = PHASES.get(arm.get('phase')) if state == 'grasping' and camera_live else None
    titles = {'offline': '运行程序未连接', 'waiting_wake': '等待唤醒', 'waiting_start': '等待启动口令',
              'preparing': '准备识别', 'recognizing': '正在识别', 'announcing': '正在播报',
              'grasping': '执行抓取与投放', 'fault': '运行异常', 'stopped': '程序已停止'}
    descriptions = {'offline': '启动独立语音程序后，画面与状态会自动连接',
                    'waiting_wake': '说“你好小亚”，回应后说“开始垃圾分拣”',
                    'waiting_start': '已唤醒 · 请说“开始垃圾分拣”',
                    'preparing': '机械臂进入原有观察姿态', 'recognizing': '等待连续稳定识别结果',
                    'announcing': '分类语音播放完成后进入动作流程',
                    'grasping': '动作指令阶段 · '+(phase or '正在执行'),
                    'fault': '请检查设备连接与运行日志', 'stopped': '显示窗口可保持打开'}
    completed = state == 'waiting_wake' and status.get('last_result') == 'official_grasp_callback_completed'
    step = {'waiting_wake': 4 if completed else 0, 'waiting_start': 0, 'preparing': 1,
            'recognizing': 1, 'announcing': 2, 'grasping': 3}.get(state, -1)
    thumbnail = records/('cycle-%03d-detection.jpg' % max(0, int(number(status.get('cycles')))))
    try:
        thumbnail_valid = confirmed and thumbnail.is_file() and thumbnail.stat().st_mtime >= started
    except OSError:
        thumbnail_valid = False
    return dict(online=online, runtime_pid=boot.get('pid') if alive else None, state=state,
                status_generation=status.get('generation'),
                status_runtime_session_id=status.get('runtime_session_id'),
                title=titles.get(state, '等待状态更新'), description=descriptions.get(state, ''),
                error=status.get('error') or (live.get('camera_error') if matches else None),
                camera_live=camera_live, image_path=str(preview/'latest.jpg'),
                frame_at=number(live.get('frame_at')) if matches else None,
                image_key=(live.get('pid'), live.get('sequence')) if camera_live else None,
                camera_message='相机画面暂不可用' if online else '等待运行程序连接',
                label=label, category=category, confirmed=confirmed, completed=completed,
                step=step, awake=awake, cycles=max(0, int(number(status.get('cycles')))),
                executed=max(0, int(number(status.get('grasp_calls')))), timeline=timeline(events),
                thumbnail=str(thumbnail) if thumbnail_valid else None)
