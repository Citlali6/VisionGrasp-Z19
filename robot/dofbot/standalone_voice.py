"""Independent voice -> recognition -> spoken class -> one official grasp.

No phone, Flask or APP mode is used. The bootstrap supplies the existing vendor
single-object action, camera and verified observation-pose callback.
"""
from collections import deque
from pathlib import Path
import json
import math
import os
import queue
import signal
import subprocess
import threading
import time

from voice_bridge import FrameParser, SINGLE_CLASSES, SINGLE_AUDIO

LABEL_CHINESE = dict(zip((
    'Zip_top_can', 'Old_school_bag', 'Newspaper', 'Book', 'Toilet_paper',
    'Peach_pit', 'Cigarette_butts', 'Disposable_chopsticks', 'Egg_shell',
    'Apple_core', 'Watermelon_rind', 'Fish_bone', 'Expired_tablets',
    'Expired_cosmetics', 'Used_batteries', 'Syringe'), (
    '易拉罐', '旧书包', '报纸', '书本', '卫生纸', '桃核', '烟头', '一次性筷子',
    '鸡蛋壳', '苹果核', '西瓜皮', '鱼骨', '过期药片', '过期化妆品', '废电池', '注射器')))
CATEGORY_CHINESE = {'01': '可回收垃圾', '02': '其他垃圾', '03': '厨余垃圾', '04': '有害垃圾'}


class CycleCancelled(RuntimeError):
    pass


class Session:
    """Injectable synchronous cycle; receiver only enqueues while not busy."""
    def __init__(self, *, prepare, detect, play, grasp, enable_motion=False,
                 clock=time.monotonic, sleep=time.sleep, save=lambda status: None,
                 clear_input=lambda: None, recognized=lambda frame, label, xy: None):
        self.prepare, self.detect, self.play, self.grasp = prepare, detect, play, grasp
        self.enable_motion = bool(enable_motion)
        self.clock, self.sleep, self.save = clock, sleep, save
        self.clear_input, self.recognized = clear_input, recognized
        self.lock = threading.RLock()
        self.busy = self.stopping = False
        self.generation = 0
        self.state, self.last_result = 'waiting_wake', None
        self.error = None
        self.awake_at = None
        self.language = 'cn'
        self.events = deque(maxlen=200)
        self.event_count = self.cycles = self.grasp_calls = self.recognition_frames = 0
        self.label = self.category = None
        self.stable_frames = 0
        self.event('ready', enable_motion=self.enable_motion)

    def snapshot(self):
        with self.lock:
            return dict(state=self.state, busy=self.busy, error=self.error,
                        enable_motion=self.enable_motion, last_result=self.last_result,
                        awake=self.awake_at is not None and 0 <= self.clock()-self.awake_at <= 20,
                        language=self.language, cycles=self.cycles, grasp_calls=self.grasp_calls,
                        recognition_frames=self.recognition_frames, stable_frames=self.stable_frames,
                        label=self.label, labelChinese=LABEL_CHINESE.get(self.label),
                        category=self.category, categoryChinese=CATEGORY_CHINESE.get(self.category),
                        physical_grasp_verified=False, phone_required=False,
                        event_count=self.event_count, events=list(self.events))

    def event(self, name, **details):
        with self.lock:
            self.event_count += 1
            self.events.append(dict(event=name, at=time.time(), **details))
            self.save(self.snapshot())

    def transition(self, state, **details):
        with self.lock:
            self.state = state
            self.event(state, **details)

    def fail(self, error):
        with self.lock:
            self.error = str(error)
            self.awake_at = None
            self.state = 'fault'
            self.event('fault', error=self.error)

    def request_stop(self):
        with self.lock:
            self.stopping = True
            self.awake_at = None
            self.event('stop_requested', active_action_allowed_to_return=self.busy)

    def _check(self):
        with self.lock:
            if self.stopping or self.error:
                raise CycleCancelled(self.error or 'stop requested')

    def handle(self, wake, command, raw='', received_at=None, generation=None):
        with self.lock:
            now = self.clock()
            at = now if received_at is None else received_at
            if self.busy or self.stopping or self.error:
                self.event('input_rejected', reason='busy_stopped_or_fault', raw=raw)
                return False
            if (generation is not None and generation != self.generation) or not 0 <= now-at <= 20:
                self.event('input_rejected', reason='expired_input_generation', raw=raw)
                return False
            self.event('voice_frame', wake=wake, command=command, raw=raw)
            if wake in range(1, 7) and command == 0:
                self.awake_at = at
                self.language = 'cn' if wake <= 3 else 'en'
                self.state = 'waiting_start'
                self.event('wake_received', language=self.language)
                is_wake = True
            # Official vocabulary includes both "start sorting" (92) and
            # "start garbage sorting" (108). The connected module emits 92.
            elif wake == 0 and command in (92, 108):
                if self.awake_at is None or not 0 <= now-self.awake_at <= 20:
                    self.awake_at = None
                    self.state = 'waiting_wake'
                    self.event('input_rejected', reason='wake_required')
                    return False
                self.busy = True
                self.generation += 1
                self.awake_at = None
                self.cycles += 1
                self.recognition_frames = self.stable_frames = 0
                self.label = self.category = None
                self.last_result = None
                self.clear_input()
                self.event('start_accepted', cycle=self.cycles, command=command)
                is_wake = False
            else:
                self.event('ignored_command', command=command)
                return False
        if is_wake:
            try:
                self._check()
                self.play(0, self.language)
                self.event('wake_audio_completed')
            except Exception as exc:
                self.fail('wake_audio: '+repr(exc))
            return False
        try:
            self._cycle()
        except CycleCancelled as exc:
            self.last_result = 'cancelled'
            self.event('cycle_cancelled', reason=str(exc))
        except Exception as exc:
            self.last_result = 'failed'
            self.fail(repr(exc))
        finally:
            with self.lock:
                self.generation += 1
                self.clear_input()
                self.busy = False
                self.awake_at = None
                self.state = 'fault' if self.error else 'stopped' if self.stopping else 'waiting_wake'
                self.event('cycle_finished', result=self.last_result)
        return True

    def _cycle(self):
        self._check()
        self.transition('preparing')
        if self.enable_motion:
            # The injected vendor callback sends the verified observation pose
            # and waits for its specified motion duration before returning.
            self.prepare()
        else:
            self.event('dry_run_prepare_skipped')
        self._check()
        self.transition('recognizing')
        deadline = self.clock()+20
        anchor_name, anchor_xy, last_valid = None, None, None
        selected = None
        while self.clock() < deadline:
            self._check()
            started = self.clock()
            frame, msg = self.detect()
            finished = self.clock()
            self._check()
            self.recognition_frames += 1
            name = next(reversed(msg), None) if isinstance(msg, dict) else None
            xy = None
            try:
                if name in SINGLE_CLASSES and len(msg[name]) == 2:
                    xy = tuple(float(v) for v in msg[name])
                    if not all(math.isfinite(v) for v in xy):
                        xy = None
            except (TypeError, ValueError, OverflowError):
                xy = None
            fresh = finished-started <= 1.5 and finished <= deadline
            if xy is None or not fresh:
                self.stable_frames = 0
                anchor_name, anchor_xy, last_valid = None, None, None
            else:
                stable = (name == anchor_name and last_valid is not None
                          and finished-last_valid <= 1.5 and math.dist(xy, anchor_xy) <= .005)
                self.stable_frames = self.stable_frames+1 if stable else 1
                if not stable:
                    anchor_name, anchor_xy = name, xy
                last_valid = finished
                self.label, self.category = name, SINGLE_CLASSES[name][1]
                if self.stable_frames >= 3:
                    selected = (frame, name, xy)
                    break
            if self.recognition_frames % 10 == 0:
                self.event('recognition_progress', frames=self.recognition_frames,
                           stable_frames=self.stable_frames)
            self.sleep(.05)
        if selected is None:
            self.last_result = 'no_stable_target_timeout'
            self.event('recognition_timeout', timeout_seconds=20, grasp_started=False)
            return
        frame, name, xy = selected
        self.recognized(frame, name, xy)
        self._check()
        self.transition('announcing', audio_id=SINGLE_AUDIO[name], label=name,
                        labelChinese=LABEL_CHINESE[name], category=self.category,
                        categoryChinese=CATEGORY_CHINESE[self.category])
        # play() must block and raise on failure. Grasp is unreachable until
        # the classification audio process has exited successfully.
        self.play(SINGLE_AUDIO[name], self.language)
        self.event('classification_audio_completed', audio_id=SINGLE_AUDIO[name])
        self._check()
        if self.enable_motion:
            self.transition('grasping', category=self.category)
            self.grasp_calls += 1
            self.grasp(self.category)
            self.sleep(1)  # Vendor final home command takes 1000 ms.
            self.last_result = 'official_grasp_callback_completed'
            self.event('grasp_callback_completed', physical_success_claimed=False)
        else:
            self.last_result = 'dry_run_completed'
            self.event('dry_run_grasp_skipped', category=self.category)


class BlockingPlayer:
    def __init__(self):
        self.lock = threading.Lock()

    def __call__(self, number, language):
        suffix = '_en' if language == 'en' else ''
        path = Path('/home/yahboom/speech_music')/('answer'+str(number)+suffix+'.mp3')
        if not path.is_file():
            raise FileNotFoundError(str(path))
        env = os.environ.copy()
        env.update(XDG_RUNTIME_DIR='/run/user/'+str(os.getuid()),
                   PULSE_SERVER='unix:/run/user/'+str(os.getuid())+'/pulse/native',
                   PULSE_SINK='alsa_output.usb-C-Media_Electronics_Inc._USB_Audio_Device-00.analog-stereo')
        with self.lock:
            result = subprocess.run(['mpg123', '-q', '-o', 'pulse', str(path)], env=env,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=30)
        if result.returncode:
            raise RuntimeError('Audio playback failed: '+result.stderr.decode(errors='replace')[-1000:])


def run(single, camera, prepare, record_dir, enable_motion=False):
    """Run until signal/keyboard stop. status.json is a read-only status file.

    single needs only garbage_identify.garbage_run and single_garbage_grap.
    prepare must wait until the supplied official observation move completes.
    camera.get_frame must supply a fresh image; no inference occurs while idle.
    """
    import serial
    from serial.tools import list_ports

    record_dir = Path(record_dir)
    record_dir.mkdir(parents=True, exist_ok=True)
    status_path = record_dir/'status.json'
    incoming = queue.Queue(maxsize=64)
    parser = FrameParser()
    stop = threading.Event()
    port = None

    def save(status):
        temp = record_dir/'status.tmp'
        temp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(status_path)

    def clear_input():
        parser.buffer.clear()
        while True:
            try: incoming.get_nowait()
            except queue.Empty: break
        if port is not None and port.is_open:
            port.reset_input_buffer()

    def detect():
        frame = camera.get_frame()
        if not hasattr(frame, 'shape') or len(frame.shape) != 3 or frame.shape[0] <= 0 or frame.shape[1] <= 0:
            raise RuntimeError('Camera did not provide a valid fresh image')
        return single.garbage_identify.garbage_run(frame)

    def recognized(frame, label, xy):
        import cv2
        target = record_dir/('cycle-%03d-detection.jpg' % session.cycles)
        if not cv2.imwrite(str(target), frame):
            raise RuntimeError('Could not save recognition image')
        session.event('recognition_image', path=str(target), label=label, position=list(xy))

    session = Session(prepare=prepare, detect=detect, play=BlockingPlayer(),
                      grasp=single.single_garbage_grap, enable_motion=enable_motion,
                      save=save, clear_input=clear_input, recognized=recognized)
    reader = None
    previous_handlers = {}
    try:
        device, arm = Path('/dev/myspeech'), Path('/dev/myserial')
        if not device.exists() or device.resolve() == arm.resolve():
            raise RuntimeError('Speech USB alias missing or aliases the arm')
        ports = [p for p in list_ports.comports() if p.device == str(device.resolve())]
        if len(ports) != 1 or (ports[0].vid, ports[0].pid) != (0x1a86, 0x7522):
            raise RuntimeError('Unexpected speech USB identity')
        owners = subprocess.run(['fuser', str(device)], capture_output=True)
        if owners.returncode != 1:
            raise RuntimeError('Speech port occupied or ownership check failed')
        port = serial.Serial(str(device), 115200, timeout=.05, exclusive=True)
        port.reset_input_buffer()

        def receive():
            try:
                while not stop.is_set():
                    with session.lock:
                        generation = session.generation
                    data = port.read(min(max(port.in_waiting, 1), 4096))
                    if not data:
                        continue
                    with session.lock:
                        if session.busy or generation != session.generation:
                            session.event('input_dropped_busy', raw=data.hex())
                            continue
                        for event in parser.feed(data):
                            try:
                                incoming.put_nowait((event, time.monotonic(), generation))
                            except queue.Full:
                                session.event('input_dropped_queue_full', raw=event[2])
            except Exception as exc:
                if not stop.is_set():
                    session.fail('speech_serial: '+repr(exc))

        reader = threading.Thread(target=receive, name='standalone-voice-input', daemon=True)
        reader.start()
        session.event('serial_open', device=str(device), resolved=str(device.resolve()))
        if threading.current_thread() is threading.main_thread():
            def request_stop(signum, frame):
                stop.set()
                session.request_stop()
            for signum in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[signum] = signal.signal(signum, request_stop)
        while not stop.is_set():
            try:
                event, received_at, generation = incoming.get(timeout=.1)
            except queue.Empty:
                continue
            session.handle(*event, received_at=received_at, generation=generation)
    except KeyboardInterrupt:
        session.request_stop()
    except Exception as exc:
        session.fail(repr(exc))
        raise
    finally:
        stop.set()
        if port is not None:
            port.close()
        if reader is not None:
            reader.join(timeout=.5)
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        session.transition('fault' if session.error else 'stopped', speech_port_closed=True)
    return session.snapshot()
