"""Non-display RGB888 PL frame transport and per-frame statistics identity."""
from host.libpspl.python.pspl import Device, VIDEO_ID
from host.libpspl.python.registers import COMMON as R, VIDEO as V


class VideoFrontend:
    def __init__(self, config):
        self.config = dict(config)
        self.device = Device(config["library_path"], config["uio_path"], VIDEO_ID,
                             config.get("map_size", 4096), config.get("timeout_ms", 5000))
        self._configured = False

    def open(self):
        self.device.open()
        try:
            self.configure(self.config)
        except Exception:
            self.close()
            raise
        return self

    def configure(self, config):
        width, height = int(config["width"]), int(config["height"])
        gains, biases = config.get("gains", [256]*3), config.get("biases", [0]*3)
        roi = config.get("roi", [0, 0, width-1, height-1])
        hsv = config["hsv"]  # Explicit raw HSV units, never guessed from old profile.
        if not 1 <= width <= 4096 or not 1 <= height <= 4096:
            raise ValueError("Frame outside 1..4096")
        if len(gains) != 3 or any(not isinstance(x, int) or not 0 <= x <= 1024 for x in gains):
            raise ValueError("Three Q8.8 gains required")
        if len(biases) != 3 or any(not isinstance(x, int) or not -255 <= x <= 255 for x in biases):
            raise ValueError("Three signed biases required")
        if len(roi) != 4 or not 0 <= roi[0] <= roi[2] < width or not 0 <= roi[1] <= roi[3] < height:
            raise ValueError("Invalid inclusive ROI")
        if len(hsv) != 6 or any(not isinstance(x, int) or not 0 <= x <= 255 for x in hsv):
            raise ValueError("HSV expects [hmin,hmax,smin,smax,vmin,vmax], uint8")
        if hsv[2] > hsv[3] or hsv[4] > hsv[5]:
            raise ValueError("Invalid saturation/value thresholds")
        if hsv[0] > 179 or hsv[1] > 179:
            raise ValueError("Hue thresholds use the pinned HSV range 0..179")
        with self.device.lock:
            self.device.reset()
            self.device.write(V['WIDTH'], width)
            self.device.write(V['HEIGHT'], height)
            for i, value in enumerate(gains):
                self.device.write(V['GAIN_R']+4*i, value)
            for i, value in enumerate(biases):
                self.device.write(V['BIAS_R']+4*i, value & 0xffffffff)
            # Threshold packing is the ABI's three lower/upper uint8 channels.
            self.device.write(V['HSV_MIN'], hsv[0] | (hsv[2]<<8) | (hsv[4]<<16))
            self.device.write(V['HSV_MAX'], hsv[1] | (hsv[3]<<8) | (hsv[5]<<16))
            for i, value in enumerate(roi):
                self.device.write(V['ROI_XMIN']+4*i, value)
            self.device.write(V['CONFIG_ID'], int(config["config_version"]))
            self.device.write(R['CONTROL'], 8 | (2 if config.get("bypass", False) else 0))
            if self.device.read(R['ERROR']) or not (self.device.read(R['STATUS'])&8):
                raise RuntimeError("PL rejected video configuration")
            self.device.write(R['CONTROL'], 1 | (2 if config.get("bypass", False) else 0))
        self.width, self.height = width, height
        self.config = dict(config)
        self._configured = True

    def process(self, rgb, identity):
        import numpy as np
        if not self._configured:
            raise RuntimeError("Open and configure frontend first")
        if rgb.dtype != np.uint8 or rgb.shape != (self.height, self.width, 3):
            raise ValueError("PL input must match configured RGB888 dimensions")
        for key in ("camera_id", "session_id", "frame_id", "transform_id"):
            if key not in identity:
                raise ValueError("Missing frame identity: " + key)
        raw = rgb.reshape(-1, 3).astype(np.uint32)
        words = (raw[:, 0]<<16) | (raw[:, 1]<<8) | raw[:, 2]
        words[0] |= 1<<24
        words[self.width-1::self.width] |= 1<<25
        try:
            output, stats = self.device.video(words.tolist(), self.width, self.height)
            if stats['config_version'] != self.config['config_version']:
                raise RuntimeError("Frame configuration version differs from requested profile")
        except Exception:
            self._configured = False
            raise
        pixels = np.asarray(output, dtype=np.uint32)
        result = np.stack(((pixels>>16)&255, (pixels>>8)&255, pixels&255), axis=1)
        stats["pl_frame_id"] = stats.pop("frame_id")
        stats.update(identity)
        stats["source"] = "pl_rgb"
        stats["centroid"] = ([stats["sum_x"]/stats["count"], stats["sum_y"]/stats["count"]]
                             if stats["count"] else None)
        stats["mask"] = ((pixels>>26)&1).astype(np.uint8).reshape(self.height, self.width)
        return result.astype(np.uint8).reshape(rgb.shape), stats

    def close(self):
        self._configured = False
        self.device.close()
