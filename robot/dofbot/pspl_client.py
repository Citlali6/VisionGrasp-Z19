"""Optional bounded PS HTTP client; import/construction perform no I/O."""
import base64
import json
import math
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
                 timeout_s=1., max_age_s=2., voice_source='serial_id'):
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
        self.task_id = self.session_id = self.last_result = None
        self.last_frame = -1
        self.consumed_permits = set()
        self.last_voice_sequence = 0
        self.voice_session_id = None

    def request(self, path, payload):
        body = json.dumps(payload,allow_nan=False).encode('utf-8')
        request = urllib.request.Request(self.endpoint+path,data=body,method='POST',
                    headers={'Content-Type':'application/json','Authorization':'Bearer '+self.token})
        started = time.monotonic()
        # No ambient proxy is used for the explicitly selected local PS host.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request,timeout=self.timeout_s) as response:
                if response.headers.get_content_type() != 'application/json':
                    raise RuntimeError('PS response has wrong content type')
                raw = response.read(MAX_MESSAGE+1)
                if len(raw)>MAX_MESSAGE:
                    raise RuntimeError('PS response too large')
                result = json.loads(raw,parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except (urllib.error.URLError,ValueError) as exc:
            raise RuntimeError('PS request failed: '+str(exc)) from exc
        elapsed = time.monotonic()-started
        if elapsed>self.timeout_s or type(result) is not dict:
            raise RuntimeError('PS request expired or invalid JSON object')
        return result,elapsed

    def begin(self, timeout_s=20):
        if self.task_id is not None:
            raise RuntimeError('client task already active')
        task_id = uuid.uuid4().hex
        result,_ = self.request('/task',dict(task_id=task_id,timeout_s=timeout_s,voice_source=self.voice_source))
        if (result.get('task_id') != task_id or result.get('state') != 'running' or
                not result.get('session_id') or result.get('voice_source')!=self.voice_source):
            raise RuntimeError('PS task start was not acknowledged')
        self.task_id,self.session_id = task_id,result['session_id']
        self.last_frame,self.last_result = -1,None

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
                envelope.get('schema')!='visiongrasp.ps-task/1'):
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
        self.last_frame = frame_id
        self.last_result = result
        candidate = result.get('candidate',{})
        if candidate.get('state')!='permitted':
            return None,{}
        permit = (self.session_id,candidate.get('guard_job_id'),candidate.get('permit_count'))
        if permit in self.consumed_permits or candidate.get('frame_sequence')!=frame_id:
            raise RuntimeError('repeated or wrong-frame candidate permit')
        detections = result.get('detections')
        if (result.get('association',{}).get('state')!='associated' or
                not isinstance(detections,list) or len(detections)!=1):
            raise RuntimeError('candidate lacks unique semantic correspondence')
        detection = detections[0]
        for key in ('camera_id','session_id','frame_id','transform_id'):
            if detection.get(key)!=result.get(key):
                raise RuntimeError('detection source differs from frame')
        import cv2
        import numpy as np
        raw = base64.b64decode(result['preview_jpeg_base64'],validate=True)
        if len(raw)>512*1024:
            raise RuntimeError('preview too large')
        frame = cv2.imdecode(np.frombuffer(raw,dtype=np.uint8),cv2.IMREAD_COLOR)
        space = result['image_space']
        if frame is None or frame.shape[:2]!=(space['height'],space['width']):
            raise RuntimeError('preview shape differs from result pixel space')
        self.consumed_permits.add(permit)
        return frame,{detection['label']:vendor_stability_proxy(detection['pixel_center'],space['width'],space['height'])}

    def voice_event(self):
        result,elapsed = self.request('/voice',{})
        if result.get('voice_source')!=self.voice_source or result.get('error'):
            raise RuntimeError('PS voice source differs or failed')
        session = result.get('session_id')
        initial = self.voice_session_id is None
        if self.voice_session_id is not None and session!=self.voice_session_id:
            raise RuntimeError('PS voice session changed; restart task receiver')
        self.voice_session_id = session
        event = result.get('event')
        if event is None:
            return None
        age,sequence = event.get('producer_age_s'),event.get('sequence')
        if (event.get('source')!='usb_pcm_pl' or event.get('session_id')!=session or
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
