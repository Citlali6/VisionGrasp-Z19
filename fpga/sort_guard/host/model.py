"""Offline logical register model, not hardware evidence or an AXI timing model.

Time advances only via advance(cycles). Register accesses take no simulated
clocks. The RTL testbench remains the authority for clock and bus timing.
"""
from . import guard_client as r


class SoftwareGuard:
    def __init__(self):
        self.writes = []
        self.external_busy = False
        self.reset()

    def reset(self):
        self.shadow = {offset: 0 for offset in r.CFG+r.FRAME_REGS}
        self.config = None
        # rst_n clears internal registers, not the externally driven input.
        self.active = self.ready = self.busy = False
        self.consumed = self.timed_out = self.cancelled = self.bus_fault = False
        self.job = self.sequence = self.stable = self.age = self.permits = self.permit_job = self.reason = 0
        self.anchor = None

    def _stop(self, reason):
        self.active = self.ready = False
        self.stable, self.anchor, self.reason = 0, None, reason

    def _fault(self, message):
        self.bus_fault = True
        raise OSError('simulated SLVERR: '+message)

    def _clear_stability(self, reason):
        self.ready, self.stable, self.anchor, self.reason = False, 0, None, reason

    def set_external_busy(self, value):
        self.external_busy = bool(value)
        if self.external_busy and self.active:
            self._stop(8)
            self.cancelled = True

    def advance(self, cycles):
        if type(cycles) is not int or cycles < 0:
            raise ValueError('cycles must be nonnegative integer')
        if self.active:
            timeout = self.config[0x068]
            if self.age+cycles >= timeout:
                self.age = timeout
                self._stop(6)
                self.timed_out = True
            else:
                self.age += cycles

    def read32(self, offset):
        if offset in self.shadow:
            return self.shadow[offset]
        values = {
            r.ID: r.EXPECTED_ID, r.VERSION: r.EXPECTED_VERSION, r.COMMAND: 0,
            r.BUSY: int(self.busy),
            r.STATUS: (int(self.active) | int(self.ready) << 1
                       | int(self.busy or self.external_busy) << 2
                       | int(self.consumed) << 3 | int(self.timed_out) << 4
                       | int(self.cancelled) << 5 | int(self.bus_fault) << 6),
            r.ACTIVE_JOB: self.job, r.LAST_SEQ: self.sequence,
            r.STABLE_COUNT: self.stable, r.AGE_CYCLES: self.age,
            r.PERMIT_COUNT: self.permits, r.PERMIT_JOB: self.permit_job,
            r.LAST_REASON: self.reason,
        }
        if offset not in values:
            self._fault('invalid read address')
        return values[offset]

    def write32(self, offset, value):
        self.writes.append((offset, value))
        if type(value) is not int or not 0 <= value <= 0xffffffff:
            self._fault('write value is not uint32')
        if offset in self.shadow:
            narrow = (0x048, 0x04c, 0x050, 0x054, 0x060, 0x064,
                      0x088, 0x08c, 0x090, 0x094)
            if offset in narrow and value > 65535:
                self._fault('nonzero upper bits')
            if offset == 0x098 and value & ~3:
                self._fault('reserved frame flags')
            self.shadow[offset] = value
            return
        if offset == r.BUSY:
            if value not in (0, 1):
                self._fault('reserved busy bits')
            self.busy = bool(value)
            if self.busy and self.active:
                self._stop(8)
                self.cancelled = True
            return
        if offset != r.COMMAND:
            self._fault('invalid write address')
        if value == r.CLEAR_FAULT:
            self.bus_fault = False
            return
        if value == r.CANCEL:
            self._stop(8 if self.busy or self.external_busy else 7)
            self.cancelled = True
            return
        if value not in (r.ARM, r.FRAME_COMMIT, r.CONSUME):
            self._fault('invalid command')
        if self.busy or self.external_busy:
            self._fault('busy')
        if self.active and self.age >= self.config[0x068]-1:
            self.age = self.config[0x068]
            self._stop(6)
            self.timed_out = True
            self._fault('timeout boundary')
        if value == r.ARM:
            s = self.shadow
            if (self.active or s[0x040] == 0 or s[0x048] > s[0x050]
                    or s[0x04c] > s[0x054] or s[0x058] == 0
                    or s[0x05c] < s[0x058] or s[0x060] == 0 or s[0x068] == 0):
                self._fault('ARM requires inactive valid configuration')
            self.config = {offset: s[offset] for offset in r.CFG}
            self.active, self.ready = True, False
            self.consumed = self.timed_out = self.cancelled = False
            self.job, self.sequence = s[0x040], s[0x044]
            self.stable, self.age, self.anchor, self.reason = 0, 0, None, 1
            return
        if not self.active:
            self._fault('no active task')
        if value == r.CONSUME:
            if not self.ready:
                self._fault('not ready')
            self.permits = (self.permits+1) & 0xffffffff
            self.permit_job, self.consumed = self.job, True
            self._stop(9)
            return
        s, c = self.shadow, self.config
        if s[0x09c] != self.job:
            self._fault('wrong frame job')
        if not r.newer(s[0x080], self.sequence):
            return
        self.sequence = s[0x080]
        if s[0x098] != 3:
            self._clear_stability(4)
            return
        self.age = 0
        box = tuple(s[offset] for offset in (0x088, 0x08c, 0x090, 0x094))
        x0, y0, x1, y1 = box
        if not (c[0x048] <= x0 <= x1 <= c[0x050]
                and c[0x04c] <= y0 <= y1 <= c[0x054]
                and c[0x058] <= s[0x084] <= c[0x05c]):
            self._clear_stability(4)
            return
        if self.anchor is None:
            self.anchor, self.stable = box, 1
        elif any(abs(a-b) > c[0x064] for a, b in zip(self.anchor, box)):
            self._clear_stability(5)
            return
        else:
            self.stable = min(self.stable+1, c[0x060])
        self.ready = self.stable >= c[0x060]
        self.reason = 3 if self.ready else 2
