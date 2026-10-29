"""Best-effort display side channel. No camera/arm ownership or control calls."""
from pathlib import Path
from functools import wraps
import json
import os
import threading
import time


class ArmObserver:
    """Report the verified vendor command sequence, never physical success."""
    DESTINATIONS = {'01': (27, 110, 0, 40, 265), '02': (137, 80, 35, 40, 265),
                    '03': (152, 110, 0, 40, 265), '04': (45, 80, 35, 40, 265)}

    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.Lock()
        self.value = dict(phase='idle', category=None, at=clock(), evidence='display_only')
        self.steps, self.index = [], 0
        self.active = self.returned = False
        self.error = None

    def set_phase(self, phase, category=None):
        with self.lock:
            self.value = dict(phase=phase, category=category, at=self.clock(), evidence='runtime_stage')

    def begin(self, category, grip=135):
        with self.lock:
            self.active, self.returned, self.index = True, False, 0
            self.value = dict(phase='grasping', category=category, at=self.clock(), evidence='runtime_stage')
            dest = self.DESTINATIONS.get(category)
            if dest is None:
                self.steps = []
                return
            high = (90, 80, 50, 50, 265, grip)
            self.steps = [
                ('array', (high, 1000), 'grasping'),
                ('single', (6, 30, 500), 'grasping'),
                ('array', ((90, 40, 30, 72, 265, 30), 500), 'grasping'),
                ('single', (6, grip, 500), 'grasping'),
                ('array', (high, 1000), 'transferring'),
                ('single', (1, dest[0], 500), 'transferring'),
                ('array', (dest+(grip,), 1000), 'transferring'),
                ('single', (6, 30, 500), 'releasing'),
                ('array', ((dest[0], 80, 50, 50, 265, 30), 1000), 'returning'),
                ('array', ((90, 90, 15, 20, 90, 30), 1000), 'returning'),
            ]

    def observe(self, kind, args, kwargs):
        with self.lock:
            if not self.active or not self.steps:
                return
            normalized = (tuple(args[0]), args[1]) if kind == 'array' and len(args) == 2 else tuple(args)
            expected = self.steps[self.index] if self.index < len(self.steps) else None
            if kwargs or expected is None or (kind, normalized) != expected[:2]:
                self.steps = []
                self.value.update(phase='grasping', at=self.clock(), evidence='unrecognized_sequence_coarse_only')
                return
            self.index += 1
            self.value.update(phase=expected[2], at=self.clock(), evidence='serial_write_completed',
                              command_index=self.index)

    def finish(self):
        with self.lock:
            self.active = False
            self.returned = True

    def reconcile(self, status):
        """Session's final sleep completes before its waiting_wake record."""
        with self.lock:
            events = status.get('events', [])
            latest = max((event.get('at', 0) for event in events if isinstance(event, dict)), default=0)
            if self.returned and latest >= self.value['at']:
                if status.get('state') in ('waiting_wake', 'waiting_start') and not status.get('busy'):
                    self.value = dict(phase='idle', category=self.value['category'], at=latest,
                                      evidence='session_cycle_finished')
                    self.returned = False
                elif status.get('state') == 'fault':
                    self.value.update(phase='fault', at=latest, evidence='session_fault')

    def snapshot(self):
        with self.lock:
            return dict(self.value)


def observe_sdk(arm, observer, successful_writes):
    """Pass through each call once; notify only after a successful serial write."""
    original = {}
    for name, kind in (('Arm_serial_servo_write6_array', 'array'), ('Arm_serial_servo_write', 'single')):
        method = getattr(arm, name)
        original[name] = method

        def make_wrapper(native, call_kind):
            @wraps(native)
            def wrapper(*args, **kwargs):
                try:
                    before = successful_writes()
                except Exception as exc:
                    before = None
                    observer.error = repr(exc)[-1000:]
                result = native(*args, **kwargs)
                try:
                    if before is not None and successful_writes() > before:
                        observer.observe(call_kind, args, kwargs)
                except Exception as exc:
                    observer.error = repr(exc)[-1000:]
                return result
            return wrapper
        setattr(arm, name, make_wrapper(method, kind))
    return original


class PreviewPublisher:
    def __init__(self, directory, camera_snapshot, *, pid, session_started_at,
                 observer=None, control_status_path=None, encode=None, clock=time.time):
        self.directory = Path(directory)
        self.camera_snapshot = camera_snapshot
        self.pid, self.started = pid, session_started_at
        self.observer = observer or ArmObserver(clock)
        self.control_status_path = Path(control_status_path) if control_status_path else None
        self.encode = encode or self._jpeg
        self.clock = clock
        self.stop_event = threading.Event()
        self.thread = None
        self.preview_error = None
        self.last = dict(sequence=0, frame_at=None, camera_error=None)
        self.image_sequence = None
        self.active = False

    @staticmethod
    def _jpeg(frame):
        import cv2
        height, width = frame.shape[:2]
        if width > 640 or height > 480:
            ratio = min(640/width, 480/height)
            frame = cv2.resize(frame, (max(1, int(width*ratio)), max(1, int(height*ratio))))
        okay, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not okay:
            raise RuntimeError('JPEG encoding failed')
        return encoded.tobytes()

    def _atomic(self, name, payload):
        target = self.directory/name
        temporary = self.directory/(name+'.%s.tmp' % self.pid)
        with temporary.open('wb') as output:
            output.write(payload)
        temporary.replace(target)

    def _metadata(self):
        now = self.clock()
        at = self.last.get('frame_at')
        active = self.active and not self.stop_event.is_set()
        live = bool(active and isinstance(at, (int, float)) and 0 <= now-at <= 1.5
                    and not self.last.get('camera_error') and not self.preview_error
                    and self.image_sequence == self.last.get('sequence'))
        return dict(pid=self.pid, session_started_at=self.started, active=active,
                    frame_at=at, sequence=self.last.get('sequence', 0),
                    image_sequence=self.image_sequence, camera_live=live,
                    camera_error=self.last.get('camera_error'), updated_at=now,
                    preview_error=self.preview_error or self.observer.error,
                    arm=self.observer.snapshot())

    def _write_metadata(self):
        data = json.dumps(self._metadata(), ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self._atomic('live.json', data)

    def publish_once(self):
        try:
            snapshot = self.camera_snapshot()
            if snapshot is not None:
                frame = snapshot.get('frame')
                self.last = {key: snapshot.get(key) for key in ('sequence', 'frame_at', 'camera_error')}
                at = self.last['frame_at']
                fresh = isinstance(at, (float, int)) and 0 <= self.clock()-at <= 1.5
                if (frame is not None and fresh and not self.last['camera_error']
                        and self.last['sequence'] != self.image_sequence):
                    payload = self.encode(frame)
                    self._atomic('latest.jpg', payload)
                    self.image_sequence = self.last['sequence']
            if self.control_status_path is not None:
                try:
                    status = json.loads(self.control_status_path.read_text(encoding='utf-8'))
                    if isinstance(status, dict):
                        self.observer.reconcile(status)
                except (OSError, ValueError):
                    pass
            self.preview_error = None
            self._write_metadata()
            return True
        except Exception as exc:
            self.preview_error = repr(exc)[-1000:]
            try:
                self._write_metadata()
            except Exception:
                pass
            return False

    def start(self):
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            # New generation is visible without an image before the first frame.
            (self.directory/'latest.jpg').unlink(missing_ok=True)
            self.active = True
            self._write_metadata()
            self.thread = threading.Thread(target=self._loop, name='voice-display-preview', daemon=True)
            self.thread.start()
            return True
        except Exception as exc:
            self.preview_error = repr(exc)[-1000:]
            self.active = False
            return False

    def _loop(self):
        while not self.stop_event.is_set():
            started = time.monotonic()
            self.publish_once()
            self.stop_event.wait(max(0, .125-(time.monotonic()-started)))

    def close(self):
        self.stop_event.set()
        self.active = False
        try:
            if self.thread is not None and self.thread.is_alive():
                self.thread.join(timeout=.5)
            self._write_metadata()
        except Exception as exc:
            self.preview_error = repr(exc)[-1000:]
