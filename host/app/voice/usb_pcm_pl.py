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
PHRASES = {"小助手": ("wake", 1, 0), "你好小助手": ("wake", 1, 0),
           "开始分拣": ("start", 0, 92), "开始垃圾分拣": ("start", 0, 92),
           "停止": ("cancel", 0, 0), "取消任务": ("cancel", 0, 0)}


def task_grammar(model):
    """Segment Chinese phrases into words present in this actual Vosk model."""
    grammar, kinds, known = ["[unk]"], set(), {}
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
    if kinds != {"wake", "start", "cancel"}:
        raise RuntimeError("Vosk model vocabulary cannot represent wake/start/cancel task phrases")
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
                confidence=confidence)


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
        self._closed = False

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

    def events(self, stopping, task_id):
        """Yield events with producer-local age, never cross-host clock deltas.

        The caller supplies a task binding and handles wake/start/cancel in its
        existing task state machine. Partial ASR hypotheses never yield events.
        """
        if not self.started:
            raise RuntimeError("Call start() before consuming USB PCM events")
        if not isinstance(task_id, str) or not task_id or len(task_id) > 128:
            raise ValueError("Explicit bounded task_id required")
        # Closing arecord interrupts its bounded read, allowing prompt stop.
        finished = threading.Event()
        def stop_capture():
            while not finished.wait(0.1):
                if stopping.is_set():
                    self.capture.close()
                    return
        stopper = threading.Thread(target=stop_capture, daemon=True)
        stopper.start()
        try:
            while not stopping.is_set():
                # Estimate oldest sample age from the start of this chunk read.
                captured_at = time.monotonic()
                pcm = self.capture.read()
                if stopping.is_set():
                    break
                processed_pcm = self.frontend.process(pcm)
                with self._asr_lock:
                    complete = self.recognizer.AcceptWaveform(processed_pcm)
                    result = json.loads(self.recognizer.Result()) if complete else None
                if stopping.is_set():
                    break
                if not complete:
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
                             event_sequence=self._event_sequence, asr_location="Z19_PS_ARM",
                             asr_model_id=self.config.get("vosk_model_id", Path(self.config["vosk_model"]).name),
                             audio_device=self.capture.device,
                             producer_age_seconds=max(0.0, now - captured_at))
                yield self.selection.accept(event)
        except Exception:
            # A discontinuity invalidates both filter history and ASR history.
            if not stopping.is_set():
                raise
        finally:
            finished.set()
            stopper.join(timeout=1)
            self.close()

    def close(self):
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            self.started = False
            try:
                if self.capture is not None:
                    self.capture.close()
                    self.capture.release_pipes()
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
