"""Reuse the PL guard with explicitly identified semantic or color evidence.

The legacy RTL/AXI ABI is unchanged. Its numeric count register carries bbox
area only in semantic_bbox mode, and real PL mask count in color_association
mode. Neither PS geometry nor color statistics are relabelled as the other.
"""
from dataclasses import dataclass
import math
import time
from fpga.sort_guard.host.guard_client import GuardClient, Config, READY, ACTIVE_JOB, PERMIT_JOB
from fpga.sort_guard.host.validation import StreamIdentity, ValidationError, finite, integer
from .class_mapping import business

POLICIES = ('semantic_bbox', 'color_association')


@dataclass(frozen=True)
class SemanticFrame:
    identity: StreamIdentity
    request_id: int
    requested_at: float
    sequence: int
    frame: int
    width: int
    height: int
    count: int
    bbox: tuple
    captured_at: float
    published_at: float
    target_key: tuple

    @property
    def binding(self):
        return (self.identity, self.request_id, self.requested_at,
                self.width, self.height, self.target_key)


def parse_semantic_status(status, *, identity, now, max_age):
    """Validate PS detector geometry, never manufacture a PL color status."""
    if not isinstance(identity, StreamIdentity) or type(status) is not dict:
        raise ValidationError('supervised semantic candidate identity required')
    if (status.get('schema') != 'visiongrasp.ps-semantic-candidate/1' or
            status.get('source') != 'Z19_PS_CPU_YOLO' or
            status.get('count_basis') != 'bbox_area_px' or
            status.get('camera_running') is not True):
        raise ValidationError('wrong semantic candidate source or count basis')
    if any(status.get(k) != getattr(identity, k) for k in ('camera_id', 'session_id')):
        raise ValidationError('semantic acquisition identity differs')
    now, max_age = finite(now, 'now'), finite(max_age, 'max_age')
    if not 0 < max_age <= 2:
        raise ValidationError('max_age must be in (0,2] seconds')
    requested = finite(status.get('requested_at'), 'requested_at')
    captured = finite(status.get('captured_at'), 'captured_at')
    published = finite(status.get('published_at'), 'published_at')
    if not requested <= captured <= published <= now or now-captured > max_age:
        raise ValidationError('semantic timestamps are stale or out of order')
    width = integer(status.get('width'), 'width', 1, 4096)
    height = integer(status.get('height'), 'height', 1, 4096)
    box = status.get('bbox')
    if type(box) is not list or len(box) != 4:
        raise ValidationError('semantic integer bbox required')
    box = tuple(integer(v, 'bbox', 0, 4095) for v in box)
    x0,y0,x1,y1 = box
    if not 0 <= x0 <= x1 < width or not 0 <= y0 <= y1 < height:
        raise ValidationError('semantic bbox outside frame')
    area = integer(status.get('bbox_area_px'), 'bbox_area_px', 1, width*height)
    if area != (x1-x0+1)*(y1-y0+1):
        raise ValidationError('semantic area is inconsistent with bbox')
    label = status.get('label')
    if not isinstance(label,str) or business(label) is None:
        raise ValidationError('unsupported semantic label')
    mapping = business(label)
    if status.get('category_code') != mapping['category_code']:
        raise ValidationError('semantic business category differs')
    model, transform = status.get('model_id'), status.get('transform_id')
    if any(not isinstance(v,str) or not v.strip() or len(v)>256 for v in (model,transform)):
        raise ValidationError('semantic model and transform identity required')
    target = (model, transform, integer(status.get('config_version'), 'config_version'),
              integer(status.get('class_id'), 'class_id'), label, mapping['category_code'])
    return SemanticFrame(identity, integer(status.get('request_id'), 'request_id', 1),
                         requested, integer(status.get('sequence'), 'sequence'),
                         integer(status.get('pl_frame_id'), 'pl_frame_id'), width, height,
                         area, box, captured, published, target)


class SemanticGuardClient(GuardClient):
    """Only the input validator differs; all register/task rules are inherited."""
    def _parse(self, status, identity, now):
        try:
            return parse_semantic_status(status, identity=identity, now=now, max_age=self.max_age)
        except (ValidationError, ValueError):
            if self.job_id is not None:
                self.cancel()
            raise


class CandidateGuard:
    def __init__(self, transport, config, policy):
        if policy not in POLICIES:
            raise ValueError('explicit candidate policy required')
        client = SemanticGuardClient if policy == 'semantic_bbox' else GuardClient
        self.client = client(transport, max_age=float(config.get('max_age_s', 2.0)))
        self.config = config
        self.policy = policy
        self.active = False
        self.used_job = 0
        self.segment = None

    def initialize(self):
        self.client.initialize()
        self.used_job = max(self.client.transport.read32(ACTIVE_JOB),
                            self.client.transport.read32(PERMIT_JOB))

    def cancel(self):
        if self.client.initialized:
            self.client.cancel()
        self.active = False
        self.segment = None

    def offer(self, *, task, identity, stats, detections, model_id, association,
              captured_at, width, height):
        if len(detections) != 1:
            self.cancel()
            return self.result('not_applicable', reason='semantic_target_not_unique')
        if self.policy == 'color_association' and association.get('state') != 'associated':
            self.cancel()
            return self.result('not_applicable', reason=association.get('reason'))
        detection = detections[0]
        if any(stats.get(k) != v or detection.get(k) != v for k,v in identity.as_dict().items()):
            self.cancel()
            raise ValidationError('candidate detection and PL frame identity differ')
        now = time.monotonic()
        if now-captured_at > self.client.max_age:
            self.cancel()
            return self.result('not_applicable', reason='producer_frame_expired')
        cfg = self.config
        segment = (self.policy, model_id, detection['class_id'], detection['label'],
                   detection['category_code'], identity.transform_id, stats['config_version'])
        if self.active and self.segment != segment:
            self.cancel()
        self.segment = segment
        if self.policy == 'semantic_bbox':
            edges = detection['bbox']
            if (len(edges) != 4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in edges) or
                    not 0 <= edges[0] < edges[2] <= width or not 0 <= edges[1] < edges[3] <= height):
                raise ValidationError('invalid continuous semantic bbox')
            # Cover the continuous detector rectangle with inclusive pixel cells.
            x0,y0 = math.floor(edges[0]),math.floor(edges[1])
            x1,y1 = math.ceil(edges[2])-1,math.ceil(edges[3])-1
            status = dict(schema='visiongrasp.ps-semantic-candidate/1', source='Z19_PS_CPU_YOLO',
                          count_basis='bbox_area_px', camera_running=True,
                          camera_id=identity.camera_id, session_id=identity.session_id,
                          transform_id=identity.transform_id, config_version=stats['config_version'],
                          model_id=model_id, class_id=detection['class_id'], label=detection['label'],
                          category_code=detection['category_code'], request_id=task['job_id'],
                          requested_at=task['requested_at'], sequence=identity.frame_id,
                          pl_frame_id=stats['pl_frame_id'], width=width, height=height,
                          captured_at=captured_at, published_at=now, bbox=[x0,y0,x1,y1],
                          bbox_area_px=(x1-x0+1)*(y1-y0+1))
            low,high = cfg['min_bbox_area'],cfg['max_bbox_area']
        else:
            status = self.color_status(task, identity, stats, captured_at, now, width, height)
            low,high = cfg['min_mask'],cfg['max_mask']
        binding = StreamIdentity(identity.camera_id, identity.session_id)
        if not self.active:
            self.used_job += 1
            if self.used_job > 0xffffffff:
                raise RuntimeError('guard job sequence exhausted; explicit restart required')
            config = Config(tuple(cfg['roi']), low, high, cfg['required'], cfg['jitter'], cfg['timeout_cycles'])
            self.client.arm(status, identity=binding, now=now, config=config, job_id=self.used_job)
            self.active = True
            return self.result('collecting', guard_job_id=self.used_job)
        snapshot = self.client.feed(status, identity=binding, now=now)
        if snapshot['status'] & READY:
            permit = self.client.consume(status, identity=binding, now=time.monotonic())
            self.active = False
            return self.result('permitted', guard_job_id=permit.job_id,
                               frame_sequence=permit.frame_sequence, permit_count=permit.permit_count,
                               stable=snapshot['stable'],
                               physical_grasp_verified=False)
        return self.result('collecting', guard_job_id=self.used_job, stable=snapshot['stable'])

    def result(self, state, **fields):
        return dict(state=state, policy=self.policy, target_source='Z19_PS_CPU_YOLO',
                    count_basis='bbox_area_px' if self.policy == 'semantic_bbox' else 'pl_mask_pixels',
                    **fields)

    def color_status(self, task, identity, stats, captured_at, now, width, height):
        cfg = self.config
        count, bbox = stats['count'], list(stats['bbox'])
        request = dict(request_id=task['job_id'], color=cfg['color'],
                       min_s=cfg['min_s'], min_v=cfg['min_v'],
                       requested_monotonic=task['requested_at'])
        # Source name is the existing ABI's PS assertion of real PL statistics,
        # not a claim that this new profile is the old hardware bitstream.
        return dict(source='Z19_USB_TO_REAL_PL', camera_running=True, camera_error=None,
                      camera_id=identity.camera_id, session_id=identity.session_id,
                      request=request, request_id=task['job_id'], color=cfg['color'],
                      min_s=cfg['min_s'], min_v=cfg['min_v'],
                      capture_sequence=identity.frame_id, pl_sequence=identity.frame_id,
                      frame=stats['pl_frame_id'], width=width, height=height,
                      captured_monotonic=captured_at, published_monotonic=now,
                      age_s=now-captured_at, mask_count=count, bbox=bbox,
                      target=dict(state='found', bbox=bbox, mask_count=count,
                                  frame_sequence=identity.frame_id, request_id=task['job_id']))
