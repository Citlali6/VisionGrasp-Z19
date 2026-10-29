"""Offline checks for the capture/PCM helper used by the Z19 color voice chain.

No microphone, subprocess, recognizer or other hardware is opened by this suite.
"""
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.voice import audio


class AudioTests(unittest.TestCase):
    def make_wav(self, root, rate, channels, samples, width=2):
        path = root / 'input.wav'
        with wave.open(str(path), 'wb') as stream:
            stream.setnchannels(channels)
            stream.setsampwidth(width)
            stream.setframerate(rate)
            stream.writeframes(struct.pack('<%dh' % len(samples), *samples))
        return path

    def test_stereo_mix_and_integer_downsampling(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_wav(Path(directory), 48000, 2,
                                 [100, 300, 200, 400, 300, 500,
                                  -100, -300, -200, -400, -300, -500])
            pcm = b''.join(audio.wav_pcm(path))
            self.assertEqual(struct.unpack('<2h', pcm), (300, -300))
            self.assertEqual(struct.unpack('<2h', b''.join(audio.wav_pcm(path, 'left'))),
                             (200, -200))

    def test_pcm16_roundtrip_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'recording.wav'
            samples = struct.pack('<4h', -32768, -1, 0, 32767)
            audio.write_wav(target, [samples[:4], samples[4:]])
            self.assertEqual(b''.join(audio.wav_pcm(target)), samples)
            with self.assertRaises(FileExistsError):
                audio.write_wav(target, [b'\0\0'])
            self.assertEqual(b''.join(audio.wav_pcm(target)), samples)

    def test_unsupported_wav_rate_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_wav(Path(directory), 44100, 1, [1, 2, 3])
            with self.assertRaisesRegex(ValueError, 'WAV requires'):
                list(audio.wav_pcm(path))

    def test_capture_constructs_without_opening_device(self):
        with patch.object(audio.subprocess, 'Popen') as spawn:
            capture = audio.AlsaCapture(chunk_ms=20)
            self.assertEqual(capture.chunk_bytes, 640)
            capture.close()
            spawn.assert_not_called()

    def test_capture_chunk_limits(self):
        for value in (0, 19, 501):
            with self.assertRaises(ValueError):
                audio.AlsaCapture(chunk_ms=value)

    def test_device_selection_requires_unambiguous_usb(self):
        with patch.object(audio, 'devices', return_value=[]):
            with self.assertRaisesRegex(RuntimeError, 'found 0'):
                audio.select_device()
        candidates = [dict(usb=True, alsa='plughw:1,0'),
                      dict(usb=True, alsa='plughw:2,0')]
        with patch.object(audio, 'devices', return_value=candidates):
            with self.assertRaisesRegex(RuntimeError, 'found 2'):
                audio.select_device()
        self.assertEqual(audio.select_device('plughw:CARD=Device,DEV=0'),
                         'plughw:CARD=Device,DEV=0')
        with self.assertRaises(ValueError):
            audio.select_device('plughw:1,0; echo bad')

    def test_capture_read_collects_partial_chunks(self):
        capture = audio.AlsaCapture(chunk_ms=20)
        capture.process = Mock()
        with patch.object(audio.select, 'select', return_value=([True], [], [])), \
                patch.object(audio.os, 'read', side_effect=[b'a' * 100, b'b' * 540]) as read:
            self.assertEqual(capture.read(), b'a' * 100 + b'b' * 540)
        self.assertEqual([call.args[1] for call in read.call_args_list], [640, 540])

    def test_capture_stall_and_eof_are_errors(self):
        capture = audio.AlsaCapture()
        capture.process = Mock()
        with patch.object(audio.select, 'select', return_value=([], [], [])):
            with self.assertRaisesRegex(RuntimeError, 'stalled'):
                capture.read()
        capture.errors.append('device disconnected')
        with patch.object(audio.select, 'select', return_value=([True], [], [])), \
                patch.object(audio.os, 'read', return_value=b''):
            with self.assertRaisesRegex(RuntimeError, 'device disconnected'):
                capture.read()

    def test_capture_close_terminates_and_reaps_child(self):
        capture = audio.AlsaCapture()
        capture.process = Mock()
        capture.process.poll.return_value = None
        capture.close()
        capture.process.terminate.assert_called_once_with()
        capture.process.wait.assert_called_once_with(timeout=2)
        capture.process.kill.assert_not_called()
        capture.release_pipes()
        capture.process.stdout.close.assert_called_once_with()
        capture.process.stderr.close.assert_called_once_with()

    def test_capture_close_kills_unresponsive_child(self):
        capture = audio.AlsaCapture()
        capture.process = Mock()
        capture.process.poll.return_value = None
        capture.process.wait.side_effect = [subprocess.TimeoutExpired('arecord', 2), 0]
        capture.close()
        capture.process.kill.assert_called_once_with()
        self.assertEqual(capture.process.wait.call_count, 2)


if __name__ == '__main__':
    unittest.main()
