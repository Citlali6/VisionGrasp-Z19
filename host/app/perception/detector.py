"""Pure image -> real YOLO detections. No ROS, Arm_Lib, camera or serial imports."""
import importlib
import importlib.metadata
from pathlib import Path
from .class_mapping import BUSINESS, EXCLUDED
from .model_manifest import ModelDependencyError
from .preprocess import vendor_bgr
from .postprocess import decode_results


class Detector:
    def __init__(self, manifest):
        self.manifest, self.model = manifest, None

    def load(self):
        """Explicit runtime initialization; never called during source delivery."""
        self.manifest.check_files()
        for package, expected in self.manifest.versions.items():
            try:
                actual = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError as exc:
                raise ModelDependencyError('backend package missing: '+package) from exc
            if actual != expected:
                raise ModelDependencyError('%s version %s != manifest %s' % (package, actual, expected))
        # The legally supplied source tree must already be installed for the
        # target AArch64 Python. Never load VM x86 wheels or insert a guessed tree.
        ultralytics = importlib.import_module('ultralytics')
        location = Path(ultralytics.__file__).resolve()
        expected_root = self.manifest.framework_root.resolve()
        if expected_root not in location.parents:
            raise ModelDependencyError('imported ultralytics differs from audited framework_root')
        try:
            model = ultralytics.YOLO(str(self.manifest.weights), task='detect')
            actual = model.names
            names = tuple(actual[i] for i in range(len(actual)))
            if names != self.manifest.names:
                raise ModelDependencyError('weights class order differs from manifest')
            if any(name not in BUSINESS and name not in EXCLUDED for name in names):
                raise ModelDependencyError('model contains unaudited business labels')
            self.model = model
        except ModelDependencyError:
            raise
        except Exception as exc:
            raise ModelDependencyError('real YOLO model initialization failed') from exc

    def infer(self, rgb, identity):
        if self.model is None:
            raise ModelDependencyError('explicit load() has not completed')
        height, width = rgb.shape[:2]
        bgr = vendor_bgr(rgb)
        # Supplying numpy BGR preserves the vendor invocation. NMS/letterbox
        # behavior is pinned by hashed backend sources and these explicit args.
        results = self.model.predict(source=bgr, task='detect', device='cpu',
                                     imgsz=self.manifest.image_size, batch=1,
                                     conf=self.manifest.confidence, iou=self.manifest.iou,
                                     max_det=self.manifest.max_detections,
                                     rect=True, half=False, augment=False,
                                     agnostic_nms=False, verbose=False, save=False,
                                     stream=False)
        return decode_results(results, self.manifest, identity, width, height)
