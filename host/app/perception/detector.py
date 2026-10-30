"""Pure image -> real YOLO detections. No ROS, Arm_Lib, camera or serial imports."""
import importlib
from pathlib import Path
import platform
from .class_mapping import BUSINESS, EXCLUDED
from .model_manifest import ModelDependencyError
from .preprocess import vendor_bgr
from .postprocess import decode_results


class Detector:
    def __init__(self, manifest):
        self.manifest, self.model = manifest, None

    def load(self):
        """Explicit runtime initialization; never called during source delivery."""
        if self.model is not None:
            raise ModelDependencyError('detector already loaded')
        try:
            self.manifest.check_files()
            target=self.manifest.target_environment
            if (platform.machine().lower() not in ('aarch64','arm64') or platform.system()!=target['os'] or
                    platform.python_version()!=target['python'] or
                    platform.libc_ver()!=(target['libc']['name'],target['libc']['version'])):
                raise ModelDependencyError('runtime architecture/Python/libc differs from AArch64 target record')
            modules={}
            for library,expected in self.manifest.versions.items():
                modules[library]=importlib.import_module(library)
                actual=str(getattr(modules[library],'__version__',''))
                if actual!=expected:
                    raise ModelDependencyError('%s version %s != target record %s' % (library,actual,expected))
            # cv2.__version__ supports an audited apt-installed OpenCV too; do
            # not require an unrelated opencv-python wheel distribution name.
            ultralytics=modules['ultralytics']
            location=Path(ultralytics.__file__).resolve()
            expected_root=self.manifest.framework_root.resolve()
            if expected_root not in location.parents:
                raise ModelDependencyError('imported ultralytics differs from audited framework_root')
            imported_entry=location.relative_to(expected_root).as_posix()
            if imported_entry not in self.manifest.framework_files:
                raise ModelDependencyError('imported loader is absent from audited source inventory')
            model = ultralytics.YOLO(str(self.manifest.weights), task='detect')
            actual = model.names
            names = tuple(actual[i] for i in range(len(actual)))
            if names != self.manifest.names:
                raise ModelDependencyError('weights class order differs from manifest')
            if any(name not in BUSINESS and name not in EXCLUDED for name in names):
                raise ModelDependencyError('model contains unaudited business labels')
            stride=getattr(getattr(model,'model',None),'stride',None)
            if stride is None:
                raise ModelDependencyError('loaded backend exposes no auditable model stride')
            values=stride.detach().cpu().reshape(-1).tolist() if hasattr(stride,'detach') else stride
            if not isinstance(values,(list,tuple)):
                values=[values]
            if (not values or any(float(v)!=int(v) or int(v)<=0 for v in values) or
                    max(int(v) for v in values)!=self.manifest.model_stride):
                raise ModelDependencyError('actual loaded model stride differs from source contract')
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
                                     rect=self.manifest.preprocess['rect'], half=False, augment=False,
                                     agnostic_nms=False, verbose=False, save=False,
                                     stream=False)
        return decode_results(results, self.manifest, identity, width, height)
