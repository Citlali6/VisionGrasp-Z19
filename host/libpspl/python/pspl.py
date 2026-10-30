"""ctypes binding for libpspl. No library/device is opened by construction."""
import ctypes as C
import os
import struct
import threading

VIDEO_ID = 0x56475632
AUDIO_ID = 0x56474132
GUARD_ID = 0x31444753


class _Stats(C.Structure):
    _fields_ = [(k, C.c_uint32) for k in
                ("frame_id", "count", "xmin", "ymin", "xmax", "ymax")] + [
        ("sum_x", C.c_uint64), ("sum_y", C.c_uint64),
        ("valid", C.c_uint32), ("config_version", C.c_uint32)]


class Device:
    def __init__(self, library_path, uio_path, expected_id, map_size=4096,
                 timeout_ms=5000):
        self.library_path = os.fspath(library_path)
        self.uio_path = os.fspath(uio_path)
        if expected_id not in (VIDEO_ID, AUDIO_ID, GUARD_ID):
            raise ValueError("Unknown profile device identity")
        if not 4096 <= map_size <= 0x100000 or map_size % 4:
            raise ValueError("Invalid UIO map size")
        if not 1 <= timeout_ms <= 0xffffffff:
            raise ValueError("Invalid transfer timeout")
        self.expected_id, self.map_size, self.timeout_ms = expected_id, map_size, timeout_ms
        self._lib = None
        self._handle = C.c_void_p()
        self.lock = threading.RLock()

    @staticmethod
    def _check(result):
        if result < 0:
            raise OSError(-result, os.strerror(-result))

    def open(self):
        with self.lock:
            if self._handle.value:
                raise RuntimeError("Device already open")
            lib = C.CDLL(self.library_path, use_errno=True)
            dev = C.c_void_p
            lib.pspl_open.argtypes = [C.c_char_p, C.c_uint32, C.c_size_t,
                                     C.c_uint32, C.POINTER(dev)]
            lib.pspl_open.restype = C.c_int
            lib.pspl_close.argtypes = [dev]
            lib.pspl_close.restype = None
            lib.pspl_read.argtypes = [dev, C.c_uint32, C.POINTER(C.c_uint32)]
            lib.pspl_read.restype = C.c_int
            lib.pspl_write.argtypes = [dev, C.c_uint32, C.c_uint32]
            lib.pspl_write.restype = C.c_int
            lib.pspl_reset.argtypes = [dev]
            lib.pspl_reset.restype = C.c_int
            lib.pspl_audio_process.argtypes = [dev, C.POINTER(C.c_int16),
                                              C.POINTER(C.c_int16), C.c_size_t]
            lib.pspl_audio_process.restype = C.c_int
            lib.pspl_video_process.argtypes = [dev, C.POINTER(C.c_uint32),
                C.POINTER(C.c_uint32), C.c_size_t, C.c_uint32, C.c_uint32,
                C.POINTER(_Stats)]
            lib.pspl_video_process.restype = C.c_int
            self._check(lib.pspl_open(os.fsencode(self.uio_path), self.expected_id,
                                     self.map_size, self.timeout_ms, C.byref(self._handle)))
            self._lib = lib
        return self

    def _opened(self):
        if not self._handle.value:
            raise RuntimeError("Call open() explicitly before device access")

    def close(self):
        with self.lock:
            if self._handle.value:
                self._lib.pspl_close(self._handle)
                self._handle = C.c_void_p()
                self._lib = None

    def read(self, offset):
        with self.lock:
            self._opened()
            if not isinstance(offset, int) or offset < 0 or offset % 4 or offset >= self.map_size:
                raise ValueError("MMIO offset must be aligned inside map0")
            v = C.c_uint32()
            self._check(self._lib.pspl_read(self._handle, offset, C.byref(v)))
            return v.value

    def write(self, offset, value):
        with self.lock:
            self._opened()
            if not isinstance(offset, int) or offset < 0 or offset % 4 or offset >= self.map_size:
                raise ValueError("MMIO offset must be aligned inside map0")
            if not isinstance(value, int) or not 0 <= value <= 0xffffffff:
                raise ValueError("Register value must be uint32")
            self._check(self._lib.pspl_write(self._handle, offset, value))

    def reset(self):
        with self.lock:
            self._opened()
            self._check(self._lib.pspl_reset(self._handle))

    def audio(self, pcm):
        if not isinstance(pcm, bytes) or not pcm or len(pcm) % 2:
            raise ValueError("Expected nonempty PCM16 little-endian bytes")
        # Decode explicitly: host byte order never defines the PCM contract.
        n = len(pcm) // 2
        values = struct.unpack("<%dh" % n, pcm)
        source, output = (C.c_int16 * n)(*values), (C.c_int16 * n)()
        with self.lock:
            self._opened()
            self._check(self._lib.pspl_audio_process(self._handle, source, output, n))
        return struct.pack("<%dh" % n, *output)

    def video(self, packed, width, height):
        n = width * height
        if not 1 <= width <= 4096 or not 1 <= height <= 4096 or len(packed) != n:
            raise ValueError("Frame dimensions/count mismatch")
        source, output = (C.c_uint32 * n)(*packed), (C.c_uint32 * n)()
        stats = _Stats()
        with self.lock:
            self._opened()
            self._check(self._lib.pspl_video_process(self._handle, source, output,
                                                   n, width, height, C.byref(stats)))
        result = {k: getattr(stats, k) for k, _ in stats._fields_}
        result["bbox"] = ([stats.xmin, stats.ymin, stats.xmax, stats.ymax]
                          if stats.count else None)
        return list(output), result
