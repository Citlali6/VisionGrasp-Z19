"""Explicit, injected-register client. No MMIO address, device open or motion API."""
from dataclasses import dataclass

from .validation import parse_status, integer, ValidationError

ID, VERSION, COMMAND, BUSY = 0x000, 0x004, 0x008, 0x00c
STATUS, ACTIVE_JOB, LAST_SEQ, STABLE_COUNT = 0x010, 0x014, 0x018, 0x01c
AGE_CYCLES, PERMIT_COUNT, PERMIT_JOB, LAST_REASON = 0x020, 0x024, 0x028, 0x02c
CFG = tuple(range(0x040, 0x06c, 4))
FRAME_REGS = tuple(range(0x080, 0x0a0, 4))
ARM, CANCEL, CONSUME, FRAME_COMMIT, CLEAR_FAULT = 1, 2, 4, 8, 16
ACTIVE, READY, EFFECTIVE_BUSY, CONSUMED, TIMED_OUT, CANCELLED, BUS_FAULT = (1 << n for n in range(7))
EXPECTED_ID, EXPECTED_VERSION = 0x31444753, 0x00010000


class GuardError(RuntimeError):
    pass


class TransportError(GuardError):
    pass


@dataclass(frozen=True)
class Config:
    roi: tuple
    min_mask: int
    max_mask: int
    required: int
    jitter: int
    timeout_cycles: int

    def validate(self, frame):
        if not isinstance(self.roi, (tuple, list)) or len(self.roi) != 4:
            raise ValidationError('ROI requires four inclusive PL pixel coordinates')
        x0, y0, x1, y1 = (integer(v, 'ROI coordinate', 0, 65535) for v in self.roi)
        if not (x0 <= x1 < frame.width and y0 <= y1 < frame.height):
            raise ValidationError('ROI must be within the current PL frame')
        integer(self.min_mask, 'min_mask', 1, frame.width*frame.height)
        integer(self.max_mask, 'max_mask', self.min_mask, frame.width*frame.height)
        integer(self.required, 'required', 1, 65535)
        integer(self.jitter, 'jitter', 0, 65535)
        integer(self.timeout_cycles, 'timeout_cycles', 1)


@dataclass(frozen=True)
class Permit:
    """A verified register event, never proof of grasp success or safe motion."""
    job_id: int
    frame_sequence: int
    permit_count: int


def newer(value, baseline):
    return 0 < ((value-baseline) & 0xffffffff) < 0x80000000


class GuardClient:
    """Single-owner adapter for a transport exposing read32/write32(offset,value).

    A write must return only after its bus response, and raise on SLVERR/timeout.
    The transport must provide ordering and full 32-bit writes. This class does
    not implement physical transport, discover a board, or authorize movement.
    """
    def __init__(self, transport, *, max_age=2.0):
        self.transport, self.max_age = transport, max_age
        self.initialized = False
        self.identity_verified = False
        self.frame = None
        self.job_id = None
        self.used_jobs = set()

    def _read(self, offset):
        try:
            return integer(self.transport.read32(offset), 'register value')
        except Exception as exc:
            self._io_failed()
            raise TransportError('register read failed at %#x' % offset) from exc

    def _write(self, offset, value):
        if not self.identity_verified:
            raise GuardError('device identity is not verified; write refused')
        try:
            self.transport.write32(offset, value)
        except Exception as exc:
            self._io_failed()
            raise TransportError('register write failed at %#x' % offset) from exc

    def _io_failed(self):
        verified = self.identity_verified
        self.initialized = False
        self.identity_verified = False
        self.frame = self.job_id = None
        # Best effort only: failure cannot be presented as a revoked HW permit.
        if verified:
            try:
                self.transport.write32(COMMAND, CANCEL)
            except Exception:
                pass

    def _reject(self, message):
        if self.job_id is not None:
            self.cancel()
        raise GuardError(message)

    def initialize(self):
        self.initialized = False
        self.frame = self.job_id = None
        self._verify_identity()
        if self._read(STATUS) & (ACTIVE | EFFECTIVE_BUSY | BUS_FAULT):
            raise GuardError('guard is active, busy or faulted; explicit recovery required')
        self.initialized = True

    def recover(self):
        """Explicitly cancel and clear sticky bus fault, then recheck identity."""
        self._verify_identity()
        self._write(COMMAND, CANCEL)
        self._write(COMMAND, CLEAR_FAULT)
        self.initialize()

    def _verify_identity(self):
        self.initialized = False
        self.identity_verified = False
        if (self._read(ID), self._read(VERSION)) != (EXPECTED_ID, EXPECTED_VERSION):
            raise GuardError('guard ID/version mismatch; no writes permitted')
        self.identity_verified = True

    def cancel(self):
        if not self.identity_verified:
            raise GuardError('device identity is not verified; cancel refused')
        self._write(COMMAND, CANCEL)
        self.frame = self.job_id = None
        if self._read(STATUS) & (ACTIVE | READY):
            self._io_failed()
            raise GuardError('CANCEL was not acknowledged')

    def set_busy(self, busy):
        if type(busy) is not bool:
            raise ValidationError('busy must be bool')
        if not self.initialized:
            raise GuardError('initialize first')
        self._write(BUSY, int(busy))
        if busy:
            self.frame = self.job_id = None
        state = self._read(STATUS)
        if busy and (not state & EFFECTIVE_BUSY or state & (ACTIVE | READY)):
            self._io_failed()
            raise GuardError('busy cancellation was not acknowledged')

    def _parse(self, status, identity, now):
        try:
            return parse_status(status, identity=identity, now=now, max_age=self.max_age)
        except ValidationError:
            if self.job_id is not None:
                self.cancel()
            raise

    def _snapshot(self):
        before = self._read(STATUS)
        result = dict(job=self._read(ACTIVE_JOB), sequence=self._read(LAST_SEQ),
                      permits=self._read(PERMIT_COUNT), permit_job=self._read(PERMIT_JOB),
                      stable=self._read(STABLE_COUNT), age=self._read(AGE_CYCLES),
                      reason=self._read(LAST_REASON))
        after = self._read(STATUS)
        if (before != after or result['job'] != self._read(ACTIVE_JOB)
                or result['permits'] != self._read(PERMIT_COUNT)):
            self._reject('register state changed during snapshot; re-arm required')
        if after & BUS_FAULT:
            self._reject('guard reported bus fault')
        result['status'] = after
        return result

    def arm(self, status, *, identity, now, config, job_id):
        if not self.initialized:
            raise GuardError('initialize first')
        if self.job_id is not None:
            raise GuardError('local task already active; cancel or consume it first')
        baseline = self._parse(status, identity, now)
        if not isinstance(config, Config):
            raise ValidationError('explicit Config is required')
        config.validate(baseline)
        integer(job_id, 'job_id', 1)
        if job_id in self.used_jobs:
            raise GuardError('job_id cannot be reused by this client')
        initial = self._snapshot()
        if initial['status'] & (ACTIVE | EFFECTIVE_BUSY):
            raise GuardError('hardware task is active or busy')
        if job_id in (initial['job'], initial['permit_job']):
            raise GuardError('job_id matches a retained hardware job')
        self.used_jobs.add(job_id)
        values = (job_id, baseline.sequence, *config.roi, config.min_mask,
                  config.max_mask, config.required, config.jitter, config.timeout_cycles)
        for offset, value in zip(CFG, values):
            self._write(offset, value)
        self._write(COMMAND, ARM)
        self.frame, self.job_id = baseline, job_id
        armed = self._snapshot()
        if (not armed['status'] & ACTIVE or armed['status'] & READY
                or armed['job'] != job_id or armed['sequence'] != baseline.sequence
                or armed['permits'] != initial['permits'] or armed['stable']):
            self._reject('ARM snapshot was not acknowledged')
        return armed

    def _bound(self, frame):
        if not self.initialized or self.job_id is None or self.frame is None:
            raise GuardError('no local armed task')
        if frame.binding != self.frame.binding:
            self._reject('camera/session/request/color/geometry changed; re-arm required')

    def feed(self, status, *, identity, now):
        frame = self._parse(status, identity, now)
        self._bound(frame)
        if (not newer(frame.sequence, self.frame.sequence)
                or not newer(frame.frame, self.frame.frame)
                or frame.captured_at <= self.frame.captured_at
                or frame.published_at <= self.frame.published_at):
            self._reject('duplicate, reversed or reset frame; re-arm required')
        before = self._snapshot()
        if not before['status'] & ACTIVE or before['job'] != self.job_id:
            self._reject('hardware task expired, reset or changed')
        values = (frame.sequence, frame.count, *frame.bbox, 3, self.job_id)
        for offset, value in zip(FRAME_REGS, values):
            self._write(offset, value)
        self._write(COMMAND, FRAME_COMMIT)
        after = self._snapshot()
        if (not after['status'] & ACTIVE or after['job'] != self.job_id
                or after['sequence'] != frame.sequence or after['permits'] != before['permits']):
            self._reject('frame commit was not acknowledged')
        self.frame = frame
        return after

    def consume(self, status, *, identity, now):
        frame = self._parse(status, identity, now)
        self._bound(frame)
        # Recheck the precise last committed observation immediately before
        # requesting the register event; a different fresh frame needs feed().
        if frame != self.frame:
            self._reject('consume requires the exact last committed frame')
        before = self._snapshot()
        if (before['status'] & (ACTIVE | READY | EFFECTIVE_BUSY) != (ACTIVE | READY)
                or before['job'] != self.job_id or before['sequence'] != frame.sequence):
            self._reject('guard is not ready for this frame and job')
        job = self.job_id
        self._write(COMMAND, CONSUME)
        after = self._snapshot()
        expected = (before['permits']+1) & 0xffffffff
        self.frame = self.job_id = None
        if (after['permits'] != expected or after['permit_job'] != job
                or not after['status'] & CONSUMED or after['status'] & (ACTIVE | READY)):
            self._io_failed()
            raise GuardError('CONSUME lacks an unambiguous single-permit acknowledgement')
        return Permit(job, frame.sequence, expected)
