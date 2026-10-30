"""Optional USB PCM -> PL filter -> PS Vosk -> restricted task events.

This module does not touch devices or load Vosk on import/construction. The
existing serial_id deployment remains the default. A new PS service selects
exactly one source for its session; this source never calls an actuator SDK.
"""
import argparse
import json
import math
from pathlib import Path
import signal
import threading
import time

from host.libpspl.python.pspl import AUDIO_ID, Device
from .audio import AlsaCapture
from .pl_frontend import PlAudioFrontend

SOURCE_SERIAL = "serial_id"
SOURCE_PCM = "usb_pcm_pl"
# Match the deployed Chinese interaction in docs/QUICKSTART.md. The observed
# serial event is wake=1/command=0, followed by command=92. These are task-layer
# compatibility fields; USB speech is recognized from PCM, not serial bytes.
# Session.handle retains its existing Chinese wake IDs 1..3, English IDs 4..6,
# and accepted start commands 92/108. This USB vocabulary is Chinese only.
PHRASES = {"你好小亚": ("wake", 1, 0),
           "开始分拣": ("start", 0, 92), "开始垃圾分拣": ("start", 0, 92),
           "停止": ("cancel", 0, 0), "取消任务": ("cancel", 0, 0)}
REQUIRED_PHRASES = frozenset(("你好小亚", "开始垃圾分拣"))


def task_grammar(model):
    """Segment Chinese phrases into words present in this actual Vosk model."""
    grammar, kinds, available, known = ["[unk]"], set(), set(), {}
    for phrase, (kind, _wake, _command) in PHRASES.items():
        best = {0: []}
        for end in range(1, len(phrase) + 1):
            candidates = []
            for start in range(end):
                word = phrase[start:end]
                if word not in known:
                    known[word] = model.vosk_model_find_word(word) >= 0
                if start in best and known[word]:
                    candidates.append(best[start] + [word])
            if candidates:
                best[end] = min(candidates, key=len)
        if len(phrase) in best:
            grammar.append(" ".join(best[len(phrase)]))
            kinds.add(kind)
            available.add(phrase)
    missing = REQUIRED_PHRASES - available
    if missing:
        raise RuntimeError("Vosk model vocabulary cannot represent required task phrases: " +
                           ", ".join(sorted(missing)))
    if "cancel" not in kinds:
        raise RuntimeError("Vosk model vocabulary cannot represent a restricted cancel phrase")
    return grammar


class VoiceSourceSelection:
    """One configured origin per task session; cannot mix serial and PCM."""
    def __init__(self, source=SOURCE_SERIAL):
        if source not in (SOURCE_SERIAL, SOURCE_PCM):
            raise ValueError("voice_source must be serial_id or usb_pcm_pl")
        self.source = source

    def accept(self, event):
        if event.get("audio_source") != self.source:
            raise ValueError("Voice event source differs from selected session origin")
        return event


def parse_task_result(result, minimum_confidence):
    """Only complete whitelisted Vosk results become task-layer messages."""
    text = "".join(str(result.get("text", "")).split())
    if text not in PHRASES:
        return None
    words = result.get("result") or []
    if not words:
        return None
    confidence = min(float(word.get("conf", 0)) for word in words)
    if not math.isfinite(confidence) or confidence < minimum_confidence:
        return None
    kind, wake, command = PHRASES[text]
    return dict(kind=kind, command=kind, wake_id=wake, legacy_command_id=command,
                language="cn", confidence=confidence)


class UsbPcmPlSession:
    def __init__(self, config):
        self.config = dict(config)
        self.selection = VoiceSourceSelection(self.config.get("voice_source", SOURCE_SERIAL))
        if self.selection.source != SOURCE_PCM:
            raise ValueError("USB PCM PL entry requires explicit voice_source=usb_pcm_pl")
        for key in ("library", "uio_path", "alsa_device", "vosk_model"):
            if not isinstance(self.config.get(key), str) or not self.config[key]:
                raise ValueError("Missing explicit voice configuration: " + key)
        self.minimum_confidence = self.config.get("min_confidence", 0.65)
        if (isinstance(self.minimum_confidence, bool) or
                not isinstance(self.minimum_confidence, (int, float)) or
                not math.isfinite(self.minimum_confidence) or not 0 <= self.minimum_confidence <= 1):
            raise ValueError("min_confidence must be finite within 0..1")
        device = Device(self.config["library"], self.config["uio_path"], AUDIO_ID,
                        timeout_ms=self.config.get("timeout_ms", 5000))
        self.frontend = PlAudioFrontend(device, **self.config.get("filter", {}))
        self.capture = None
        self.recognizer = None
        self.model = None
        self.started = False
        self._event_sequence = 0
        self._last_event = (None, 0.0)
        self._asr_lock = threading.Lock()
        self._close_lock = threading.RLock()
        self._capture_close_lock = threading.Lock()
        self._boundary_condition = threading.Condition(threading.RLock())
        self._boundary_request_lock = threading.Lock()
        self._boundary_requested = self._boundary_done = 0
        self._producer_active = False
        self._producer_ident = None
        self._producer_stop = None
        self._source_error = None
        self._closed = False
        self._cleanup_done = False

    def start(self):
        """Explicit initialization; failures require a new session instance."""
        if self._closed or self.started or self.capture is not None:
            raise RuntimeError("USB PCM session already initialized")
        model_path = Path(self.config["vosk_model"])
        if not model_path.is_dir():
            raise FileNotFoundError("Vosk model directory missing: " + str(model_path))
        from vosk import Model, KaldiRecognizer
        self.model = Model(str(model_path))
        grammar = task_grammar(self.model)
        self.recognizer = KaldiRecognizer(self.model, 16000,
            json.dumps(grammar, ensure_ascii=False))
        self.recognizer.SetWords(True)
        try:
            self.frontend.open()
            self.capture = AlsaCapture(device=self.config["alsa_device"], chunk_ms=100)
            self.capture.start()
            self.started = True
        except BaseException:
            self.close()
            raise
        return self

    def _check_source(self):
        # Called while holding _boundary_condition. No device I/O under it.
        if self._source_error:
            raise RuntimeError(self._source_error)
        if self._closed or not self.started or (self._producer_stop is not None and self._producer_stop.is_set()):
            raise RuntimeError("USB PCM voice source stopped")

    def _interrupt_capture(self, capture):
        # A boundary caller may close arecord to interrupt read(); the boundary
        # producer releases its pipes only after that read has returned. Serialize
        # close calls because AlsaCapture's process termination runs outside
        # its own lock.
        if capture is not None:
            with self._capture_close_lock:
                capture.close()

    @property
    def boundary_id(self):
        """Last fully acknowledged producer boundary, initially zero."""
        with self._boundary_condition:
            return self._boundary_done

    def request_boundary(self, timeout_s=8):
        """Request a producer-owned PCM/PL/ASR discontinuity and await its ID.

        Call from the authenticated service thread, never the event producer.
        No acknowledgement is issued until every old capture resource and
        filter history has been discarded and a fresh capture is running.
        """
        if (type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or
                not 0 < timeout_s <= 30):
            raise ValueError("boundary timeout must be finite within (0,30] seconds")
        end = time.monotonic() + timeout_s
        if not self._boundary_request_lock.acquire(timeout=timeout_s):
            raise TimeoutError("another USB PCM voice boundary request is still active")
        try:
            with self._boundary_condition:
                self._check_source()
                if threading.get_ident() == self._producer_ident:
                    raise RuntimeError("voice producer cannot wait for its own boundary")
                while not self._producer_active:
                    remaining = end - time.monotonic()
                    if remaining <= 0:
                        self._source_error = "USB PCM event producer did not become ready"
                        self._boundary_condition.notify_all()
                        raise TimeoutError(self._source_error)
                    self._boundary_condition.wait(remaining)
                    self._check_source()
                if self._boundary_requested == 0xffffffff:
                    raise RuntimeError("voice boundary IDs exhausted; restart source")
                self._boundary_requested += 1
                requested = self._boundary_requested
                capture = self.capture
                self._boundary_condition.notify_all()
            try:
                self._interrupt_capture(capture)
            except Exception as exc:
                with self._boundary_condition:
                    self._source_error = "could not interrupt old USB PCM capture: " + str(exc)
                    self._boundary_condition.notify_all()
                raise RuntimeError(self._source_error) from exc
            with self._boundary_condition:
                while self._boundary_done < requested:
                    self._check_source()
                    remaining = end - time.monotonic()
                    if remaining <= 0:
                        self._source_error = "USB PCM voice boundary acknowledgement timed out"
                        self._boundary_condition.notify_all()
                        raise TimeoutError(self._source_error)
                    self._boundary_condition.wait(remaining)
                self._check_source()
                if time.monotonic() > end:
                    self._source_error = "USB PCM voice boundary acknowledgement missed its deadline"
                    self._boundary_condition.notify_all()
                    raise TimeoutError(self._source_error)
                return self._boundary_done
        finally:
            self._boundary_request_lock.release()

    def _epoch_current(self, epoch):
        with self._boundary_condition:
            self._check_source()
            return epoch == self._boundary_done == self._boundary_requested

    def _apply_boundary(self):
        # This method runs only in events(), after any old read/filter/ASR call
        # has returned. close() serializes teardown against this entire rebuild.
        with self._close_lock:
            with self._boundary_condition:
                self._check_source()
                requested = self._boundary_requested
                if requested == self._boundary_done:
                    return
                old = self.capture
            self._interrupt_capture(old)
            if old is not None:
                old.release_pipes()
            with self._boundary_condition:
                self.capture = None
                self._check_source()
            self.frontend.close()
            with self._boundary_condition:
                self._check_source()
            self.frontend.open()  # Resets PL FIFO/history and starts a new PCM session.
            with self._boundary_condition:
                self._check_source()
            with self._asr_lock:
                self.recognizer.Reset()
            fresh = AlsaCapture(device=self.config["alsa_device"], chunk_ms=100)
            with self._boundary_condition:
                self._check_source()
                self.capture = fresh
            fresh.start()
            with self._boundary_condition:
                self._check_source()
                self._last_event = (None, 0.0)
                self._boundary_done = requested
                self._boundary_condition.notify_all()

    def events(self, stopping, task_id):
        """Yield events with producer-local age, never cross-host clock deltas.

        The caller supplies a task binding and handles wake/start/cancel in its
        existing task state machine. Partial ASR hypotheses never yield events.
        """
        if not self.started:
            raise RuntimeError("Call start() before consuming USB PCM events")
        if not isinstance(task_id, str) or not task_id or len(task_id) > 128:
            raise ValueError("Explicit bounded task_id required")
        with self._boundary_condition:
            self._check_source()
            if self._producer_active:
                raise RuntimeError("USB PCM source already has an event producer")
            self._producer_active = True
            self._producer_ident = threading.get_ident()
            self._producer_stop = stopping
            self._boundary_condition.notify_all()
        # Closing arecord interrupts its bounded read, allowing prompt stop.
        finished = threading.Event()
        def stop_capture():
            while not finished.wait(0.1):
                if stopping.is_set():
                    with self._boundary_condition:
                        capture = self.capture
                        self._boundary_condition.notify_all()
                    self._interrupt_capture(capture)
                    return
        stopper = threading.Thread(target=stop_capture, daemon=True)
        stopper.start()
        try:
            while not stopping.is_set():
                with self._boundary_condition:
                    self._check_source()
                    pending = self._boundary_requested != self._boundary_done
                    capture, epoch = self.capture, self._boundary_done
                if pending:
                    self._apply_boundary()
                    continue
                # Estimate oldest sample age from the start of this chunk read.
                captured_at = time.monotonic()
                try:
                    pcm = capture.read()
                except Exception:
                    if stopping.is_set():
                        break
                    with self._boundary_condition:
                        self._check_source()
                        if self._boundary_requested != self._boundary_done:
                            continue  # Expected interruption; producer owns rebuild.
                    raise
                if stopping.is_set():
                    break
                if not self._epoch_current(epoch):
                    continue  # Whole old block is discarded, including partial reads.
                processed_pcm = self.frontend.process(pcm)
                if not self._epoch_current(epoch):
                    continue
                with self._asr_lock:
                    # Capture the epoch with this specific recognition call.
                    # Boundary callers never reset the recognizer underneath it.
                    if not self._epoch_current(epoch):
                        continue
                    complete = self.recognizer.AcceptWaveform(processed_pcm)
                    result = json.loads(self.recognizer.Result()) if complete else None
                if stopping.is_set():
                    break
                if not self._epoch_current(epoch) or not complete:
                    continue
                event = parse_task_result(result, self.minimum_confidence)
                if event is None:
                    continue
                now = time.monotonic()
                if event["kind"] == self._last_event[0] and now - self._last_event[1] < 1:
                    continue
                self._last_event = (event["kind"], now)
                self._event_sequence += 1
                event.update(self.frontend.metadata())
                event.update(schema="visiongrasp.ps-voice-event/1", task_id=task_id,
                             source=SOURCE_PCM,
                             boundary_id=epoch,
                             event_sequence=self._event_sequence, asr_location="Z19_PS_ARM",
                             asr_model_id=self.config.get("vosk_model_id", Path(self.config["vosk_model"]).name),
                             audio_device=capture.device,
                             producer_age_seconds=max(0.0, now - captured_at))
                if self._epoch_current(epoch):
                    # A request can race the yield itself. Its old boundary_id
                    # remains intact; the service must filter against its ack.
                    yield self.selection.accept(event)
        except Exception as exc:
            # A discontinuity invalidates both filter history and ASR history.
            with self._boundary_condition:
                closing = self._closed
            if not stopping.is_set() and not closing:
                with self._boundary_condition:
                    if self._source_error is None:
                        self._source_error = "USB PCM voice source failed: " + str(exc)
                    self._boundary_condition.notify_all()
                raise
        finally:
            finished.set()
            stopper.join(timeout=1)
            try:
                self.close()
            finally:
                with self._boundary_condition:
                    self._producer_active = False
                    self._producer_ident = None
                    self._boundary_condition.notify_all()

    def close(self):
        # Publish cancellation before waiting for the rebuild/device locks, so
        # boundary waiters wake promptly and a concurrent rebuild cannot ack.
        with self._boundary_condition:
            self._closed = True
            self.started = False
            self._boundary_condition.notify_all()
        with self._close_lock:
            if self._cleanup_done:
                return
            self._cleanup_done = True
            try:
                if self.capture is not None:
                    self._interrupt_capture(self.capture)
                    self.capture.release_pipes()
                    self.capture = None
            finally:
                try:
                    if self.recognizer is not None:
                        with self._asr_lock:
                            self.recognizer.Reset()
                finally:
                    self.frontend.close()


def main():
    parser = argparse.ArgumentParser(description="Explicit USB PCM PL task-event source")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    stopping = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    source = UsbPcmPlSession(config)
    try:
        source.start()
        for event in source.events(stopping, args.task_id):
            print(json.dumps(event, ensure_ascii=False), flush=True)
    finally:
        source.close()


if __name__ == "__main__":
    main()
