"""Fail-closed external model contract; no model import or initialization here."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


class ModelDependencyError(RuntimeError):
    """Missing or mismatched dependencies; this is never a no-target result."""


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ModelManifest:
    model_id: str
    weights: Path
    weights_sha256: str
    names: tuple
    versions: dict
    framework_root: Path
    framework_files: dict
    image_size: int = 640
    confidence: float = 0.65
    iou: float = 0.7
    max_detections: int = 300

    @classmethod
    def read(cls, filename):
        data = json.loads(Path(filename).read_text(encoding='utf-8'))
        if data.get('schema') != 'visiongrasp.ps-model-manifest/1':
            raise ModelDependencyError('unsupported model manifest schema')
        names = data.get('names')
        if (not isinstance(names, list) or not names or
                any(not isinstance(s, str) or not s for s in names) or
                len(names) != len(set(names))):
            raise ModelDependencyError('manifest needs actual ordered model.names from matching weights/YAML')
        versions = data.get('versions', {})
        if any(not isinstance(versions.get(k), str) or not versions[k]
               for k in ('ultralytics', 'torch', 'numpy', 'opencv-python')):
            raise ModelDependencyError('exact VM-derived backend versions required')
        contract = data.get('preprocess', {})
        if contract != dict(input='RGB888', backend_input='BGR_uint8_HWC',
                            vendor_resize=[640, 480], batch=1,
                            backend='ultralytics_numpy_predictor', normalization='backend_divide_255',
                            letterbox_fill=114, rect=True, half=False, backend_nms=True):
            raise ModelDependencyError('unsupported or incomplete preprocessing contract')
        result = cls(data['model_id'], Path(data['weights']), data['weights_sha256'],
                     tuple(names), versions, Path(data['framework_root']),
                     data['framework_files'], int(data['image_size']),
                     float(data['confidence']), float(data['iou']), int(data['max_detections']))
        if (not result.model_id or len(result.weights_sha256) != 64 or
                any(c not in '0123456789abcdef' for c in result.weights_sha256) or
                result.image_size <= 0 or result.image_size % 32 or
                not 0 < result.confidence <= 1 or not 0 < result.iou < 1 or
                not 1 <= result.max_detections <= 3000):
            raise ModelDependencyError('invalid model identity or inference parameters')
        required = ('ultralytics/__init__.py', 'ultralytics/engine/predictor.py',
                    'ultralytics/models/yolo/detect/predict.py',
                    'ultralytics/data/augment.py', 'ultralytics/utils/ops.py')
        if any(k not in result.framework_files for k in required):
            raise ModelDependencyError('audited framework implementation hashes required')
        return result

    def check_files(self):
        if not self.weights.is_file():
            raise ModelDependencyError('model weights missing: '+str(self.weights))
        if sha256_file(self.weights) != self.weights_sha256:
            raise ModelDependencyError('weight SHA-256 differs from enrolled manifest')
        root = self.framework_root.resolve()
        for name, expected in self.framework_files.items():
            path = (root/name).resolve()
            if root not in path.parents or not path.is_file() or sha256_file(path) != expected:
                raise ModelDependencyError('backend source mismatch: '+name)
