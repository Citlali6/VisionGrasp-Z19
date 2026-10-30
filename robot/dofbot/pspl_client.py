"""Optional bounded PS HTTP client; import/construction perform no I/O."""
import base64
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

MAX_MESSAGE = 2*1024*1024


def vendor_stability_proxy(center, width, height):
    """Exact deployed garbage_identify (b,-a) convention for stability only.

    This affine, metre-scale IK input convention is NOT a calibrated physical
    measurement. Fixed pickup actions do not consume these values as positions.
    """
    px = int(float(center[0])*640/width)
    py = int(float(center[1])*480/height)
    a = round((320-px)/4000,5)
    b = round(((480-py)/3000)*0.8+0.17,5)
    return (b,-a)


class PsplClient:
    def __init__(self, *, endpoint, token, camera_id, transform_id,
                 timeout_s=1., max_age_s=2., voice_source='serial_id',
                 candidate_policy='semantic_bbox'):
        url = urllib.parse.urlsplit(endpoint)
        if (url.scheme not in ('http','https') or not url.hostname or url.username or
                url.password or url.query or url.fragment or url.path not in ('','/')):
            raise ValueError('endpoint must be an explicit HTTP(S) server origin')
        if not isinstance(token,str) or len(token)<32 or not camera_id or not transform_id:
            raise ValueError('token, camera_id and transform_id required')
        if not 0 < timeout_s <= 2 or not 0 < max_age_s <= 2:
            raise ValueError('request timeout and producer max age must be in (0,2] seconds')
        self.endpoint,self.token = endpoint.rstrip('/'),token
        self.camera_id,self.transform_id = camera_id,transform_id
        self.timeout_s,self.max_age_s = timeout_s,max_age_s
        if voice_source not in ('serial_id','usb_pcm_pl'):
            raise ValueError('select exactly one voice source')
        self.voice_source = voice_source
        if candidate_policy not in ('semantic_bbox','color_association'):
            raise ValueError('explicit supported candidate policy required')
        self.candidate_policy = candidate_policy
        self.task_id = self.session_id = self.last_result = None
        self.last_frame = -1
        self.consumed_permits = set()
        self.last_voice_sequence = 0
        self.voice_session_id = None
        self.voice_boundary_id = None
        self.voice_lock = threading.RLock()
        self.preview_session_id = None
        self.last_received_monotonic = self.last_age_at_receive_s = None

    def request(self, path, payload, timeout_s=None):
        deadline = self.timeout_s if timeout_s is None else timeout_s
        if type(deadline) not in (int,float) or not math.isfinite(deadline) or not 0 < deadline <= 10:
            raise ValueError('bounded HTTP deadline required')
        body = json.dumps(payload,allow_nan=False).encode('utf-8')
        request = urllib.request.Request(self.endpoint+path,data=body,method='POST',
                    headers={'Content-Type':'application/json','Authorization':'Bearer '+self.token})
        started = time.monotonic()
        # No ambient proxy is used for the explicitly selected local PS host.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request,timeout=deadline) as response:
                if response.headers.get_content_type() != 'application/json':
                    raise RuntimeError('PS response has wrong content type')
                raw = response.read(MAX_MESSAGE+1)
                if len(raw)>MAX_MESSAGE:
                    raise RuntimeError('PS response too large')
                result = json.loads(raw,parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except (urllib.error.URLError,ValueError) as exc:
            raise RuntimeError('PS request failed: '+str(exc)) from exc
        elapsed = time.monotonic()-started
        if elapsed>deadline or type(result) is not dict:
            raise RuntimeError('PS request expired or invalid JSON object')
        return result,elapsed

    def begin(self, timeout_s=20):
        if self.task_id is not None:
            raise RuntimeError('client task already active')
        task_id = uuid.uuid4().hex
        result,_ = self.request('/task',dict(task_id=task_id,timeout_s=timeout_s,voice_source=self.voice_source,
                                           candidate_policy=self.candidate_policy))
        if (result.get('task_id') != task_id or result.get('state') != 'running' or
                not result.get('session_id') or result.get('voice_source')!=self.voice_source or
                result.get('candidate_policy')!=self.candidate_policy):
            raise RuntimeError('PS task start was not acknowledged')
        if any(pin is not None and pin!=result['session_id']
               for pin in (self.preview_session_id,self.voice_session_id)):
            # Refuse to adopt a restarted producer underneath an existing
            # display/voice session, even before its next poll observes it.
            try:
                self.request('/cancel',dict(task_id=task_id))
            finally:
                raise RuntimeError('PS task session differs from pinned preview/voice session')
        self.task_id,self.session_id = task_id,result['session_id']
        self.last_frame,self.last_result = -1,None
        self.last_received_monotonic = self.last_age_at_receive_s = None

    def cancel(self):
        if self.task_id is None:
            return
        task_id = self.task_id
        try:
            result,_ = self.request('/cancel',dict(task_id=task_id))
            if result.get('task_id')!=task_id or result.get('session_id')!=self.session_id:
                raise RuntimeError('PS cancellation identity differs')
        finally:
            self.task_id,self.last_result = None,None

    def detect(self):
        """Existing detect() shape: (BGR frame, {label: vendor_stability_xy}).

        Empty messages while the real PL guard collects; only its single,
        identity-bound consumed permit supplies a semantic target to the new
        entry. A missing model/backend is propagated as an error by the service.
        """
        if self.task_id is None:
            raise RuntimeError('begin task first')
        envelope,elapsed = self.request('/result',dict(task_id=self.task_id))
        if (envelope.get('task_id') != self.task_id or envelope.get('session_id') != self.session_id or
                envelope.get('schema')!='visiongrasp.ps-task/1' or
                envelope.get('candidate_policy')!=self.candidate_policy):
            raise RuntimeError('PS task/session changed')
        if envelope.get('state') in ('cancelled','error','timeout'):
            raise RuntimeError('PS task '+envelope['state']+': '+str(envelope.get('error')))
        result = envelope.get('result')
        if result is None:
            return None,{}
        identity = dict(camera_id=self.camera_id,session_id=self.session_id,
                        task_id=self.task_id,transform_id=self.transform_id)
        if any(result.get(k)!=v for k,v in identity.items()) or result.get('schema')!='visiongrasp.ps-perception/1':
            raise RuntimeError('perception identity mismatch')
        age = result.get('producer_age_s')
        if type(age) not in (int,float) or not math.isfinite(age) or age<0 or age+elapsed>self.max_age_s:
            raise RuntimeError('PS frame expired')
        frame_id = result.get('frame_id')
        if type(frame_id) is not int or frame_id<self.last_frame:
            raise RuntimeError('PS frame sequence reversed')
        if frame_id == self.last_frame:
            return None,{}
        if result.get('selection_policy') != self.candidate_policy:
            raise RuntimeError('PS candidate policy changed within task')
        received = time.monotonic()
        frame,space = self._decode_preview(result)
        if age+elapsed+time.monotonic()-received > self.max_age_s:
            raise RuntimeError('PS frame expired during image decoding')
        self.last_frame,self.last_result = frame_id,result
        self.last_received_monotonic,self.last_age_at_receive_s = received,age+elapsed
        candidate = result.get('candidate',{})
        if candidate.get('policy') != self.candidate_policy:
            raise RuntimeError('PS permit policy differs from task contract')
        if candidate.get('state')!='permitted':
            return frame,{}
        basis = 'bbox_area_px' if self.candidate_policy=='semantic_bbox' else 'pl_mask_pixels'
        if candidate.get('count_basis') != basis or candidate.get('target_source') != 'Z19_PS_CPU_YOLO':
            raise RuntimeError('PS permit count basis/source differs from policy')
        if (type(candidate.get('guard_job_id')) is not int or
                not 1 <= candidate['guard_job_id'] <= 0xffffffff or
                type(candidate.get('permit_count')) is not int or
                not 0 <= candidate['permit_count'] <= 0xffffffff):
            raise RuntimeError('PS permit has invalid register event identity')
        permit = (self.session_id,candidate.get('guard_job_id'),candidate.get('permit_count'))
        if permit in self.consumed_permits or candidate.get('frame_sequence')!=frame_id:
            raise RuntimeError('repeated or wrong-frame candidate permit')
        detections = result.get('detections')
        if (not isinstance(detections,list) or len(detections)!=1 or
                self.candidate_policy=='color_association' and
                result.get('association',{}).get('state')!='associated'):
            raise RuntimeError('candidate lacks unique semantic correspondence')
        detection = detections[0]
        for key in ('camera_id','session_id','frame_id','transform_id'):
            if detection.get(key)!=result.get(key):
                raise RuntimeError('detection source differs from frame')
        self.consumed_permits.add(permit)
        return frame,{detection['label']:vendor_stability_proxy(detection['pixel_center'],space['width'],space['height'])}

    @staticmethod
    def _decode_preview(result):
        import cv2
        import numpy as np
        space = result['image_space']
        if any(type(space.get(k)) is not int or not 1 <= space[k] <= 4096 for k in ('width','height')):
            raise RuntimeError('preview dimensions outside profile')
        raw = base64.b64decode(result['preview_jpeg_base64'],validate=True)
        if len(raw)>512*1024:
            raise RuntimeError('preview too large')
        frame = cv2.imdecode(np.frombuffer(raw,dtype=np.uint8),cv2.IMREAD_COLOR)
        if frame is None or frame.shape[:2]!=(space['height'],space['width']):
            raise RuntimeError('preview shape differs from result pixel space')
        return frame,space

    def preview(self, after_sequence=-1):
        """Independent raw-camera display branch; never returns task permission."""
        result,elapsed = self.request('/preview',dict(after_sequence=after_sequence))
        received = time.monotonic()
        if (result.get('schema')!='visiongrasp.ps-preview/1' or
                result.get('source')!='ps_camera_preview' or result.get('pl_processed') is not False or
                result.get('camera_id')!=self.camera_id or result.get('transform_id')!=self.transform_id):
            raise RuntimeError('PS raw preview identity/source differs')
        session = result.get('session_id')
        if not isinstance(session,str) or not session or (self.preview_session_id is not None and
                session!=self.preview_session_id) or (self.session_id is not None and session!=self.session_id):
            raise RuntimeError('PS preview session changed')
        self.preview_session_id = session
        if result.get('state') in ('waiting','unchanged','stale'):
            return None
        sequence,age = result.get('frame_id'),result.get('producer_age_s')
        if (result.get('state')!='live' or type(sequence) is not int or
                not max(0,after_sequence+1) <= sequence <= 0xffffffff or
                type(age) not in (int,float) or not math.isfinite(age) or age<0):
            raise RuntimeError('invalid PS preview sequence or age')
        if age+elapsed>self.max_age_s:
            return None
        frame,_ = self._decode_preview(result)
        if age+elapsed+time.monotonic()-received>self.max_age_s:
            return None
        # Receiver-local lower bound on capture receive time. It deliberately
        # includes the whole request duration, never subtracts remote clocks,
        # and is not an exact cross-host latency/exposure timestamp.
        return dict(frame=frame,sequence=sequence,captured_monotonic=received-age-elapsed,
                    session_id=session,source='ps_camera_preview')

    def voice_event(self):
        with self.voice_lock:
            return self._voice_event()

    def reset_voice_boundary(self):
        """Discard queued busy speech before accepting a new local generation."""
        if self.voice_source != 'usb_pcm_pl':
            return
        with self.voice_lock:
            snapshot,_ = self.request('/voice',{})
            session = snapshot.get('session_id')
            if (snapshot.get('voice_source')!=self.voice_source or snapshot.get('error') or
                    not isinstance(session,str) or not session or
                    any(pin is not None and pin!=session for pin in
                        (self.session_id,self.preview_session_id,self.voice_session_id))):
                raise RuntimeError('cannot establish USB speech producer boundary')
            result,_ = self.request('/voice/boundary',dict(session_id=session),timeout_s=10)
            boundary,sequence = result.get('boundary_id'),result.get('sequence')
            if (result.get('session_id')!=session or result.get('voice_source')!=self.voice_source or
                    result.get('state')!='cleared' or type(boundary) is not int or boundary<1 or
                    type(sequence) is not int or sequence<0 or
                    self.voice_boundary_id is not None and boundary<=self.voice_boundary_id):
                raise RuntimeError('USB speech producer did not acknowledge a new boundary')
            self.voice_session_id,self.voice_boundary_id = session,boundary
            self.last_voice_sequence = sequence

    def _voice_event(self):
        result,elapsed = self.request('/voice',{})
        if result.get('voice_source')!=self.voice_source or result.get('error'):
            raise RuntimeError('PS voice source differs or failed')
        session = result.get('session_id')
        initial = self.voice_session_id is None
        if self.voice_session_id is not None and session!=self.voice_session_id:
            raise RuntimeError('PS voice session changed; restart task receiver')
        self.voice_session_id = session
        boundary = result.get('boundary_id')
        if type(boundary) is not int or boundary<0:
            raise RuntimeError('USB speech boundary is missing')
        if self.voice_boundary_id is None:
            self.voice_boundary_id = boundary
        elif boundary != self.voice_boundary_id:
            raise RuntimeError('USB speech boundary changed without receiver acknowledgement')
        event = result.get('event')
        if event is None:
            return None
        age,sequence = event.get('producer_age_s'),event.get('sequence')
        if (event.get('source')!='usb_pcm_pl' or event.get('session_id')!=session or
                event.get('boundary_id')!=self.voice_boundary_id or
                type(sequence) is not int or type(age) not in (int,float) or
                not math.isfinite(age) or age<0):
            raise RuntimeError('invalid PS voice identity or age')
        if sequence<=self.last_voice_sequence:
            return None
        self.last_voice_sequence=sequence
        if initial:
            # Establish a receiver boundary; do not replay a wake/start event
            # produced before this VM client connected.
            return None
        if age+elapsed>self.max_age_s:
            return None
        return event
