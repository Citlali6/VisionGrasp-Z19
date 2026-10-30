"""Pure 63-point Blackman-window bandpass design; called only at explicit setup.

No coefficients are generated at import. Initial 150..6500 Hz design parameters
are engineering choices, not microphone measurements or attenuation evidence.
"""
import hashlib
import math
import struct


def design_bandpass(fs=16000, low_hz=150.0, high_hz=6500.0, reference_hz=1000.0):
    values = (fs, low_hz, high_hz, reference_hz)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in values):
        raise ValueError("Finite numeric bandpass parameters required")
    if fs != 16000 or not 0 < low_hz < reference_hz < high_hz < fs / 2:
        raise ValueError("Expected fs=16000 and 0 < low < reference < high < Nyquist")
    taps = []
    for k in range(63):
        m = k - 31
        ideal = (2 * (high_hz - low_hz) / fs if m == 0 else
                 (math.sin(2 * math.pi * high_hz * m / fs) -
                  math.sin(2 * math.pi * low_hz * m / fs)) / (math.pi * m))
        window = 0.42 - 0.5 * math.cos(2 * math.pi * k / 62) + 0.08 * math.cos(4 * math.pi * k / 62)
        taps.append(ideal * window)
    response = sum(h * math.cos(2 * math.pi * reference_hz * (k - 31) / fs)
                   for k, h in enumerate(taps))
    if not math.isfinite(response) or abs(response) < 1e-12:
        raise ValueError("Degenerate FIR normalization at reference frequency")
    quantized = []
    for h in taps:
        scaled = h / response * 32768
        if not math.isfinite(scaled):
            raise ValueError("Nonfinite FIR coefficient")
        value = math.floor(scaled + 0.5) if scaled >= 0 else -math.floor(-scaled + 0.5)
        if not -32768 <= value <= 32767:
            raise ValueError("FIR coefficient exceeds signed Q1.15; revise design parameters")
        quantized.append(value)
    if not any(quantized):
        raise ValueError("Quantization removed every FIR coefficient")
    packed = struct.pack("<63h", *quantized)
    return dict(coefficients=quantized, sha256=hashlib.sha256(packed).hexdigest(),
                format="signed-Q1.15", taps=63, fs=fs, low_hz=low_hz,
                high_hz=high_hz, reference_hz=reference_hz,
                design="Blackman-window bandpass sinc; centered real-response normalization",
                rounding="nearest, ties away from zero")
