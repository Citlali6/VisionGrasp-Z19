"""Bind this profile's complete snapshots to the existing GuardClient ABI."""
import time
from fpga.sort_guard.host.guard_client import GuardClient, Config, READY, ACTIVE_JOB, PERMIT_JOB
from fpga.sort_guard.host.validation import StreamIdentity


class CandidateGuard:
    def __init__(self, transport, config):
        self.client = GuardClient(transport, max_age=float(config.get('max_age_s', 2.0)))
        self.config = config
        self.active = False
        self.used_job = 0

    def initialize(self):
        self.client.initialize()
        self.used_job = max(self.client.transport.read32(ACTIVE_JOB),
                            self.client.transport.read32(PERMIT_JOB))

    def cancel(self):
        if self.client.initialized:
            self.client.cancel()
        self.active = False

    def offer(self, *, task, identity, stats, association, captured_at, width, height):
        if association.get('state') != 'associated':
            self.cancel()
            return dict(state='not_applicable', reason=association.get('reason'))
        now = time.monotonic()
        if now-captured_at > self.client.max_age:
            self.cancel()
            return dict(state='not_applicable', reason='producer_frame_expired')
        cfg = self.config
        count, bbox = stats['count'], list(stats['bbox'])
        request = dict(request_id=task['job_id'], color=cfg['color'],
                       min_s=cfg['min_s'], min_v=cfg['min_v'],
                       requested_monotonic=task['requested_at'])
        # Source name is the existing ABI's PS assertion of real PL statistics,
        # not a claim that this new profile is the old hardware bitstream.
        status = dict(source='Z19_USB_TO_REAL_PL', camera_running=True, camera_error=None,
                      camera_id=identity.camera_id, session_id=identity.session_id,
                      request=request, request_id=task['job_id'], color=cfg['color'],
                      min_s=cfg['min_s'], min_v=cfg['min_v'],
                      capture_sequence=identity.frame_id, pl_sequence=identity.frame_id,
                      frame=stats['pl_frame_id'], width=width, height=height,
                      captured_monotonic=captured_at, published_monotonic=now,
                      age_s=now-captured_at, mask_count=count, bbox=bbox,
                      target=dict(state='found', bbox=bbox, mask_count=count,
                                  frame_sequence=identity.frame_id, request_id=task['job_id']))
        binding = StreamIdentity(identity.camera_id, identity.session_id)
        if not self.active:
            # Guard job IDs may never be reused; a loss of correspondence ends
            # that guard segment, so later valid segments get a fresh ID.
            self.used_job += 1
            if self.used_job > 0xffffffff:
                raise RuntimeError('guard job sequence exhausted; explicit restart required')
            config = Config(tuple(cfg['roi']), cfg['min_mask'], cfg['max_mask'],
                            cfg['required'], cfg['jitter'], cfg['timeout_cycles'])
            self.client.arm(status, identity=binding, now=now, config=config, job_id=self.used_job)
            self.active = True
            return dict(state='collecting', guard_job_id=self.used_job)
        snapshot = self.client.feed(status, identity=binding, now=now)
        if snapshot['status'] & READY:
            permit = self.client.consume(status, identity=binding, now=time.monotonic())
            self.active = False
            return dict(state='permitted', guard_job_id=permit.job_id,
                        frame_sequence=permit.frame_sequence, permit_count=permit.permit_count,
                        physical_grasp_verified=False)
        return dict(state='collecting', guard_job_id=self.used_job, stable=snapshot['stable'])
