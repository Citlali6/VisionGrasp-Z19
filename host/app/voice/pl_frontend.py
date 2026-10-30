"""Exclusive PCM16 PL session over the C UIO transport; no CPU fallback."""
import threading
import uuid

from host.libpspl.python.pspl import AUDIO_ID, Device
from host.libpspl.python.registers import COMMON as R, AUDIO as A
from .coefficients import design_bandpass


class PlAudioFrontend:
    def __init__(self, device, *, config_id=1, dc=True, fir=True, gate=False,
                 open_threshold=400, close_threshold=200, attack_step=1024,
                 release_step=64, low_hz=150.0, high_hz=6500.0):
        if not isinstance(device, Device) or device.expected_id != AUDIO_ID:
            raise ValueError("Explicit audio-profile Device required")
        if not isinstance(config_id, int) or not 1 <= config_id <= 0xffffffff:
            raise ValueError("config_id must be a nonzero uint32")
        if not all(type(v) is bool for v in (dc, fir, gate)):
            raise ValueError("DC/FIR/gate switches must be booleans")
        if not all(type(v) is int for v in (open_threshold, close_threshold, attack_step, release_step)):
            raise ValueError("Integer PCM thresholds and UQ1.15 steps required")
        if not 0 <= close_threshold < open_threshold <= 32768:
            raise ValueError("Gate requires 0 <= close < open <= 32768")
        if not 1 <= attack_step <= 32768 or not 1 <= release_step <= 32768:
            raise ValueError("Gate steps must be 1..32768 in UQ1.15")
        self.device, self.config_id = device, config_id
        self.flags = int(dc) | int(fir) << 1 | int(gate) << 2
        self.gate = (open_threshold, close_threshold, attack_step, release_step)
        self.band = (low_hz, high_hz)
        self.session_id = None
        self.sample_count = self.block_sequence = 0
        self.coefficient_manifest = None
        self._ready = False
        self._lock = threading.RLock()

    def open(self):
        """Explicit device open, state reset and complete coefficient commit."""
        with self._lock:
            if self._ready:
                raise RuntimeError("Audio frontend already open")
            manifest = design_bandpass(low_hz=self.band[0], high_hz=self.band[1])
            self.device.open()
            try:
                self.device.reset()
                if self.device.read(R["STATUS"]) & 4:
                    raise RuntimeError("Reset did not drain audio pipeline")
                for index, value in enumerate(manifest["coefficients"]):
                    self.device.write(A["COEFF_INDEX"], index)
                    self.device.write(A["COEFF_VALUE"], value & 0xffff)
                for offset, value in zip((A["GATE_OPEN"], A["GATE_CLOSE"], A["ATTACK"], A["RELEASE"]), self.gate):
                    self.device.write(offset, value)
                self.device.write(A["FLAGS"], self.flags)
                self.device.write(A["CONFIG_ID"], self.config_id)
                if self.device.read(A["COEFF_LOADED"]) != 63:
                    raise RuntimeError("Incomplete 63-tap coefficient staging")
                self.device.write(R["CONTROL"], 8)  # Disabled and empty CONFIG_COMMIT.
                if (not self.device.read(R["STATUS"]) & 8 or
                        self.device.read(R["CONFIG_VERSION"]) != self.config_id or self.device.read(R["ERROR"])):
                    raise RuntimeError("Audio configuration commit rejected")
                self.device.write(R["CONTROL"], 1)
                self.coefficient_manifest = manifest
                self.session_id = uuid.uuid4().hex
                self.sample_count = self.block_sequence = 0
                self._ready = True
            except BaseException:
                self.device.close()
                raise
        return self

    def process(self, pcm):
        """Preserve block order and exactly one output sample per input sample.

        The C client alternates FIFO writes/reads. Any transfer error invalidates
        the entire session; calling process again requires close()+open().
        """
        if not isinstance(pcm, bytes) or not pcm or len(pcm) % 2:
            raise ValueError("Nonempty mono S16_LE PCM with even byte count required")
        with self._lock:
            if not self._ready:
                raise RuntimeError("Call open() before PL PCM processing")
            try:
                result = self.device.audio(pcm)
                if len(result) != len(pcm) or self.device.read(R["ERROR"]):
                    raise RuntimeError("Audio sample count or PL status mismatch")
            except BaseException:
                self._ready = False
                try:
                    self.device.reset()
                except Exception:
                    # Keep the original transfer failure; closing destroys the
                    # poisoned handle even if reset itself cannot be delivered.
                    pass
                finally:
                    self.device.close()
                raise
            self.sample_count += len(pcm) // 2
            self.block_sequence += 1
            return result

    def metadata(self):
        with self._lock:
            return dict(audio_source="usb_pcm_pl", filter_location="Z19_PL",
                        session_id=self.session_id, sequence=self.block_sequence,
                        sample_count=self.sample_count, config_id=self.config_id,
                        coefficient_sha256=(self.coefficient_manifest or {}).get("sha256"),
                        rate=16000, channels=1, pcm_format="S16_LE")

    def close(self):
        with self._lock:
            was_ready, self._ready = self._ready, False
            try:
                if was_ready:
                    self.device.reset()  # Explicit session stop drops history.
            finally:
                self.device.close()
