"""Explicit PS runtime: supervised V4L2 -> PL PIO -> CPU YOLO -> bounded JSON.

No device or model initialization occurs at import/construction. Run only on a
prepared target with the new profile; source delivery does not run this module.
"""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import secrets
import signal
import threading
import time
import uuid
from pathlib import Path

from .coordinates import CoordinateMapper, associate_color, color_centroid
from .detector import Detector
from .guard_adapter import CandidateGuard
from .model_manifest import ModelManifest
from .pl_transport import VideoFrontend
from .result_types import FrameIdentity

MAX_MESSAGE = 2*1024*1024


class CameraSource:
    def __init__(self, config):
        self.config, self.capture = config, None
        self.condition = threading.Condition()
        self.stopping = threading.Event()
        self.sequence = 0
        self.latest = self.error = self.thread = None

    def open(self):
        import cv2
        path = self.config['device']
        if not isinstance(path, str) or not path.startswith('/dev/v4l/by-id/'):
            raise ValueError('camera device must be an explicit persistent V4L2 by-id path')
        self.capture = cv2.VideoCapture(path, cv2.CAP_V4L2)
        if not self.capture.isOpened():
            self.close()
            raise RuntimeError('camera could not be opened')
        self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['width'])
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['height'])
        self.capture.set(cv2.CAP_PROP_FPS, self.config['fps'])
        self.thread = threading.Thread(target=self._read, name='ps-v4l2-capture', daemon=True)
        self.thread.start()

    def _read(self):
        try:
            import cv2
            while not self.stopping.is_set():
                ok, bgr = self.capture.read()
                captured_at = time.monotonic()  # receive completion, not sensor exposure
                if not ok or bgr is None or bgr.shape != (self.config['height'], self.config['width'], 3):
                    raise RuntimeError('V4L2 read failed or negotiated image size changed')
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                with self.condition:
                    if self.sequence == 0xffffffff:
                        raise RuntimeError('capture sequence exhausted; rebuild session')
                    self.sequence += 1
                    self.latest = (self.sequence, captured_at, rgb)
                    self.condition.notify_all()
        except Exception as exc:
            with self.condition:
                self.error = str(exc)
                self.condition.notify_all()

    def next_frame(self, after, not_before, timeout):
        deadline = time.monotonic()+timeout
        with self.condition:
            while True:
                if self.error:
                    raise RuntimeError('camera stream discontinuity: '+self.error)
                if self.stopping.is_set():
                    raise RuntimeError('camera stopped')
                if self.latest and self.latest[0] > after and self.latest[1] >= not_before:
                    seq, stamp, frame = self.latest
                    return seq, stamp, frame.copy()
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('no new camera frame within capture deadline')
                self.condition.wait(remaining)

    def close(self):
        self.stopping.set()
        with self.condition:
            self.condition.notify_all()
        if self.thread:
            self.thread.join(timeout=1)
            if self.thread.is_alive():
                # A V4L2 driver read may be blocking. Never release the capture
                # from underneath that read; process exit closes its descriptor.
                return
        if self.capture:
            self.capture.release()
            self.capture = None


class Runtime:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.session_id = uuid.uuid4().hex
        self.task = self.worker = self.result = self.voice = None
        self.voice_sequence = 0
        self.audio_source = self.audio_thread = None
        self.voice_error = None
        self.voice_source = config.get('voice',{}).get('voice_source','serial_id')
        if self.voice_source not in ('serial_id','usb_pcm_pl'):
            raise ValueError('select exactly one voice source')
        self.used_tasks = set()
        self.camera = CameraSource(config['camera'])
        self.frontend = VideoFrontend(config['video'])
        self.detector = Detector(ModelManifest.read(config['model_manifest']))
        self.guard = self.guard_device = None
        if config['input_source'] not in ('pl_rgb', 'raw_rgb'):
            raise ValueError('explicit input_source must be pl_rgb or raw_rgb')
        self.width, self.height = config['video']['width'], config['video']['height']
        transform_id = config['transform_id']
        sx,sy = config['camera']['width']/self.width,config['camera']['height']/self.height
        actual_mapping = [sx,0,(sx-1)/2,0,sy,(sy-1)/2,0,0,1]
        supplied_mapping = config['pixel_to_capture']
        if (not isinstance(supplied_mapping,list) or len(supplied_mapping)!=9 or
                any(type(v) not in (int,float) or not math.isfinite(v) or abs(v-a)>1e-9
                    for v,a in zip(supplied_mapping,actual_mapping))):
            raise ValueError('pixel_to_capture must match actual OpenCV half-pixel resize; crop/rotation not selected')
        self.mapper = CoordinateMapper(camera_id=config['camera']['camera_id'],
                                       transform_id=transform_id,
                                       width=self.width, height=self.height,
                                       pixel_to_reference=config['pixel_to_capture'],
                                       reference_id=config['capture_space_id'],
                                       calibration=config.get('calibration'))
        if config.get('guard'):
            guard = config['guard']
            roi = config['video'].get('roi',[0,0,self.width-1,self.height-1])
            hsv = config['video']['hsv']
            if (guard['roi']!=roi or guard['min_s']!=hsv[2] or guard['min_v']!=hsv[4] or
                    type(guard['required']) is not int or guard['required']<3):
                raise ValueError('guard ROI/thresholds must match PL snapshot; at least three stable frames required')

    def open(self):
        from host.libpspl.python.pspl import Device
        try:
            self.frontend.open()
            self.detector.load()
            if self.config.get('guard'):
                cfg = self.config['guard']
                self.guard_device = Device(library_path=cfg['library_path'], uio_path=cfg['uio_path'],
                                           expected_id=0x31444753,
                                           timeout_ms=cfg.get('timeout_ms', 5000))
                self.guard_device.open()

                class RegisterTransport:
                    def read32(inner, offset):
                        return self.guard_device.read(offset)
                    def write32(inner, offset, value):
                        self.guard_device.write(offset, value)
                self.guard = CandidateGuard(RegisterTransport(), cfg)
                self.guard.initialize()
            self.camera.open()
            if self.voice_source == 'usb_pcm_pl':
                from host.app.voice.usb_pcm_pl import UsbPcmPlSession
                self.audio_source = UsbPcmPlSession(self.config['voice'])
                self.audio_source.start()
                self.audio_thread = threading.Thread(target=self._audio,name='ps-usb-pcm-asr',daemon=True)
                self.audio_thread.start()
        except Exception:
            self.close()
            raise

    def begin(self, payload):
        task_id = payload.get('task_id')
        timeout = payload.get('timeout_s', 20)
        if payload.get('voice_source','serial_id') != self.voice_source:
            raise ValueError('task voice source differs from configured PS/VM source')
        if (not isinstance(task_id,str) or not 1 <= len(task_id) <= 128 or
                type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0 < timeout <= 20):
            raise ValueError('task_id and finite timeout_s in (0,20] required')
        with self.lock:
            if (self.stop.is_set() or self.worker and self.worker.is_alive() or
                    self.task and self.task['state'] == 'running'):
                raise RuntimeError('runtime stopped or task busy')
            if task_id in self.used_tasks or len(self.used_tasks) >= 100000:
                raise ValueError('task_id reused or session task budget exhausted')
            self.used_tasks.add(task_id)
            now = time.monotonic()
            self.task = dict(task_id=task_id, job_id=len(self.used_tasks), state='running',
                             requested_at=now, deadline=now+timeout, cancel=threading.Event())
            self.result = None
            self.worker = threading.Thread(target=self._process, args=(self.task,), daemon=True)
            self.worker.start()
            return dict(task_id=task_id, session_id=self.session_id, state='running',voice_source=self.voice_source)

    def cancel(self, task_id):
        with self.lock:
            if self.task is None or self.task['task_id'] != task_id:
                raise ValueError('unknown task_id')
            self.task['cancel'].set()
            # Worker owns MMIO; cancellation is observed between bounded C
            # transfers/model calls. Never race a cancel register with its feed.
            return dict(task_id=task_id, session_id=self.session_id, state='cancel_requested')

    def _check(self, task):
        if self.stop.is_set() or task['cancel'].is_set():
            raise InterruptedError('task cancelled')
        if time.monotonic() >= task['deadline']:
            raise TimeoutError('task deadline expired')

    def _process(self, task):
        after = 0
        previous_label = None
        try:
            import cv2
            while True:
                self._check(task)
                seq, captured, raw = self.camera.next_frame(after, task['requested_at'],
                                                         min(1., task['deadline']-time.monotonic()))
                after = seq
                identity = FrameIdentity(self.config['camera']['camera_id'], self.session_id,
                                         seq, self.config['transform_id'])
                resized = cv2.resize(raw, (self.width,self.height), interpolation=cv2.INTER_LINEAR)
                processed, stats = self.frontend.process(resized, identity.as_dict())
                self._check(task)
                selected = processed if self.config['input_source'] == 'pl_rgb' else resized
                detections = self.detector.infer(selected, identity)
                self._check(task)
                for detection in detections:
                    detection['coordinates'] = self.mapper.map(detection['pixel_center'], identity)
                # PL keeps the whole pixel stream; only statistics are ROI
                # limited. Component matching must apply that same ROI.
                matching = dict(stats)
                matching['mask'] = stats['mask'].copy()
                rx0,ry0,rx1,ry1 = self.config['video'].get('roi',[0,0,self.width-1,self.height-1])
                matching['mask'][:ry0,:] = 0
                matching['mask'][ry1+1:,:] = 0
                matching['mask'][:,:rx0] = 0
                matching['mask'][:,rx1+1:] = 0
                association = associate_color(detections, matching, identity)
                centroid = color_centroid(stats)
                if centroid['valid']:
                    centroid['coordinates'] = self.mapper.map(centroid['pixel_xy'], identity)
                label = detections[0]['label'] if len(detections)==1 else None
                if self.guard and previous_label is not None and label != previous_label:
                    self.guard.cancel()
                previous_label = label
                candidate = (self.guard.offer(task=task, identity=identity, stats=stats,
                                            association=association, captured_at=captured,
                                            width=self.width,height=self.height)
                             if self.guard else dict(state='not_applicable', reason='guard_not_configured'))
                now = time.monotonic()
                # No image annotations enter the model. References identify the
                # acquisition and processed byte content without storing images.
                frame = dict(schema='visiongrasp.ps-perception/1', **identity.as_dict(),
                             task_id=task['task_id'], model_id=self.detector.manifest.model_id,
                             input_source=self.config['input_source'],
                             image_space=dict(width=self.width,height=self.height,
                                              pixel_format='RGB888', transform_id=identity.transform_id),
                             raw_reference=dict(sequence=seq, space=self.config['capture_space_id'],
                                                sha256=hashlib.sha256(raw.tobytes()).hexdigest()),
                             processed_reference=dict(source='pl_rgb', config_version=stats['config_version'],
                                                      sha256=hashlib.sha256(processed.tobytes()).hexdigest()),
                             pl_frame_id=stats['pl_frame_id'], config_version=stats['config_version'],
                             detections=detections, color_centroid=centroid,
                             association=association, candidate=candidate,
                             selection_policy='sole_semantic_target_and_single_contained_color_component',
                             producer_age_s=now-captured)
                ok,jpeg = cv2.imencode('.jpg', cv2.cvtColor(selected,cv2.COLOR_RGB2BGR),
                                       [cv2.IMWRITE_JPEG_QUALITY,65])
                if not ok or len(jpeg)>512*1024:
                    raise RuntimeError('bounded preview JPEG encoding failed')
                frame['preview_jpeg_base64'] = base64.b64encode(jpeg).decode('ascii')
                with self.lock:
                    self._check(task)
                    self.result = (frame, captured)
                    if candidate['state'] == 'permitted':
                        task['state'] = 'completed'
                        break
        except InterruptedError:
            with self.lock:
                task['state'], self.result = 'cancelled', None
        except TimeoutError:
            with self.lock:
                task['state'] = 'timeout'
                self.result = None
        except Exception as exc:
            with self.lock:
                task['state'], task['error'], self.result = 'error', str(exc), None
        finally:
            if self.guard and self.guard.active:
                try:
                    self.guard.cancel()
                except Exception as exc:
                    with self.lock:
                        task['state'], task['error'], self.result = 'error', 'guard_cancel: '+str(exc), None

    def snapshot(self, task_id):
        with self.lock:
            if self.task is None or task_id != self.task['task_id']:
                raise ValueError('unknown task_id')
            task = self.task
            frame = dict(self.result[0]) if self.result else None
            if frame:
                frame['producer_age_s'] = time.monotonic()-self.result[1]
            return dict(schema='visiongrasp.ps-task/1', task_id=task_id, session_id=self.session_id,
                        state=task['state'], error=task.get('error'), result=frame)

    def publish_voice(self, event):
        """Called by local USB PCM PL adapter; never accepts arbitrary motor text."""
        if event.get('source') != 'usb_pcm_pl' or event.get('command') not in ('wake','start','cancel','stop'):
            raise ValueError('unsupported voice source/command')
        initial_age = event.get('producer_age_seconds')
        if type(initial_age) not in (float,int) or not math.isfinite(initial_age) or initial_age<0:
            raise ValueError('voice producer age required')
        with self.lock:
            self.voice_sequence += 1
            self.voice = dict(event, audio_sequence=event.get('sequence'),
                              audio_session_id=event.get('session_id'),
                              sequence=self.voice_sequence, session_id=self.session_id,
                              task_id=self.task['task_id'] if self.task else None,
                              produced_at=time.monotonic()-initial_age)

    def _audio(self):
        try:
            for event in self.audio_source.events(self.stop,'voice_control'):
                self.publish_voice(event)
        except Exception as exc:
            self.voice_error = str(exc)
            self.stop.set()

    def voice_snapshot(self):
        with self.lock:
            if self.voice is None:
                return dict(session_id=self.session_id,event=None,voice_source=self.voice_source,error=self.voice_error)
            event = dict(self.voice)
            event['producer_age_s'] = time.monotonic()-event.pop('produced_at')
            return dict(session_id=self.session_id,event=event,voice_source=self.voice_source,error=self.voice_error)

    def close(self):
        self.stop.set()
        if self.audio_source:
            self.audio_source.close()
        if self.audio_thread:
            self.audio_thread.join(timeout=2)
        if self.task:
            self.task['cancel'].set()
        self.camera.close()
        if self.worker and self.worker is not threading.current_thread():
            self.worker.join(timeout=5)
            if self.worker.is_alive():
                # In-process YOLO is not forcibly killed. Do not close MMIO
                # beneath the worker; process termination releases the mapping.
                return
        self.frontend.close()
        if self.guard_device:
            self.guard_device.close()


def make_server(runtime, *, bind, port, token):
    if not bind or not 1 <= int(port) <= 65535 or not isinstance(token,str) or len(token) < 32:
        raise ValueError('explicit bind/port and at least 32-character token required')

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, format, *args):
            return  # no bearer secrets or personal frame data in request logs

        def do_POST(self):
            try:
                supplied = self.headers.get('Authorization','')
                if not secrets.compare_digest(supplied, 'Bearer '+token):
                    return self.reply(401, dict(error='unauthorized'))
                if self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('application/json required')
                if self.headers.get('Transfer-Encoding'):
                    raise ValueError('chunked requests unsupported')
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= MAX_MESSAGE:
                    raise ValueError('invalid request size')
                data = self.rfile.read(length)
                if len(data) != length:
                    raise ValueError('short request')
                payload = json.loads(data)
                if type(payload) is not dict:
                    raise ValueError('JSON object required')
                if self.path == '/task':
                    result = runtime.begin(payload)
                elif self.path == '/cancel':
                    result = runtime.cancel(payload['task_id'])
                elif self.path == '/result':
                    result = runtime.snapshot(payload['task_id'])
                elif self.path == '/voice':
                    result = runtime.voice_snapshot()
                elif self.path == '/stop':
                    runtime.stop.set()
                    result = dict(state='stop_requested')
                else:
                    return self.reply(404, dict(error='unknown_endpoint'))
                self.reply(200,result)
            except (ValueError,KeyError,TypeError) as exc:
                self.reply(400,dict(error=str(exc)))
            except RuntimeError as exc:
                self.reply(409,dict(error=str(exc)))
            except Exception:
                self.reply(500,dict(error='request_failed'))

        def reply(self, status, payload):
            body = json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8')
            if len(body)>MAX_MESSAGE:
                status,body = 500,b'{"error":"response_too_large"}'
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Connection','close')
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        request_queue_size = 4
        def __init__(self,*args):
            self.slots = threading.BoundedSemaphore(8)
            super().__init__(*args)
        def process_request(self,request,client_address):
            if not self.slots.acquire(blocking=False):
                self.shutdown_request(request)
                return
            try:
                super().process_request(request,client_address)
            except Exception:
                self.slots.release()
                raise
        def process_request_thread(self,request,client_address):
            try:
                super().process_request_thread(request,client_address)
            finally:
                self.slots.release()
    return Server((bind,int(port)),Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8'))
    token = Path(config['http']['token_file']).read_text(encoding='utf-8').strip()
    runtime = Runtime(config)
    server = make_server(runtime,bind=config['http']['bind'],port=config['http']['port'],token=token)
    previous = {}
    try:
        runtime.open()
        def stop(signum,frame):
            runtime.stop.set()
        for signum in (signal.SIGINT,signal.SIGTERM):
            previous[signum] = signal.signal(signum,stop)
        server.timeout=.2
        while not runtime.stop.is_set():
            server.handle_request()
    finally:
        server.server_close()
        runtime.close()
        for signum,handler in previous.items():
            signal.signal(signum,handler)


if __name__ == '__main__':
    main()
