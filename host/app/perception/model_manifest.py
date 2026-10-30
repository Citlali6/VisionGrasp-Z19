"""Fail-closed external model contract; no model import or initialization here."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path


class ModelDependencyError(RuntimeError):
    """Missing or mismatched dependencies; this is never a no-target result."""


LIBRARIES = ('ultralytics', 'torch', 'numpy', 'cv2')


def actual_text(value, name):
    if not isinstance(value,str) or not value.strip() or 'REQUIRED' in value:
        raise ModelDependencyError(name+' requires actual recorded metadata')
    return value


def actual_sha256(value, name):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ModelDependencyError(name+' requires an actual lowercase SHA-256')
    return value


def environment(value, name, target=False):
    if type(value) is not dict:
        raise ModelDependencyError(name+' metadata required')
    for field in ('machine','python','os'):
        actual_text(value.get(field),name+'.'+field)
    versions=value.get('versions')
    if type(versions) is not dict or not set(LIBRARIES).issubset(versions):
        raise ModelDependencyError(name+' requires exact library __version__ values')
    for library,version in versions.items():
        if not isinstance(library,str) or not all(part.isidentifier() for part in library.split('.')):
            raise ModelDependencyError(name+' version keys must be actual importable module names')
        actual_text(version,name+'.versions.'+library)
    if target:
        if value['machine'].lower() not in ('aarch64','arm64') or value['os']!='Linux':
            raise ModelDependencyError('target must describe actual AArch64 Linux, not the VM')
        libc=value.get('libc')
        if type(libc) is not dict:
            raise ModelDependencyError('target libc name/version required')
        actual_text(libc.get('name'),'target libc name')
        actual_text(libc.get('version'),'target libc version')
    return value


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
    image_size: int
    model_stride: int
    confidence: float
    iou: float
    max_detections: int
    preprocess: dict
    source_environment: dict
    target_environment: dict

    @classmethod
    def read(cls, filename):
        try:
            data=json.loads(Path(filename).read_text(encoding='utf-8'))
            return cls.from_data(data)
        except ModelDependencyError:
            raise
        except (OSError,ValueError,TypeError) as exc:
            raise ModelDependencyError('model manifest missing or unreadable: '+str(filename)) from exc

    @classmethod
    def from_data(cls, data):
        try:
            return cls._from_data(data)
        except ModelDependencyError:
            raise
        except (KeyError,TypeError,ValueError) as exc:
            raise ModelDependencyError('incomplete or malformed model manifest') from exc

    @classmethod
    def _from_data(cls, data):
        if type(data) is not dict:
            raise ModelDependencyError('model manifest must be an object')
        if data.get('schema') != 'visiongrasp.ps-model-manifest/1':
            raise ModelDependencyError('unsupported model manifest schema')
        names = data.get('names')
        if (not isinstance(names, list) or not names or
                any(not isinstance(s, str) or not s for s in names) or
                len(names) != len(set(names))):
            raise ModelDependencyError('manifest needs actual ordered model.names from matching weights/YAML')
        source=environment(data.get('source_environment'),'source_environment')
        target=environment(data.get('target_environment'),'target_environment',target=True)
        actual_text(data.get('compatibility_notes'),'source-to-target compatibility_notes')
        versions=data.get('versions')
        if versions!=target['versions']:
            raise ModelDependencyError('versions must equal the separately recorded target library versions')
        contract = data.get('preprocess', {})
        supported=dict(input='RGB888',backend_input='BGR_uint8_HWC',vendor_resize=[640,480],batch=1,
                       backend='ultralytics_numpy_predictor',normalization='backend_divide_255',
                       half=False,backend_nms=True,tensor_layout='NCHW',tensor_color='RGB',
                       tensor_dtype='float32',output='post_nms_xyxy_conf_class',
                       augment=False,agnostic_nms=False)
        if (type(contract) is not dict or any(contract.get(k)!=v for k,v in supported.items()) or
                type(contract.get('rect')) is not bool or
                type(contract.get('letterbox_fill')) is not int or not 0<=contract['letterbox_fill']<=255):
            raise ModelDependencyError('unsupported or incomplete preprocessing contract')
        # Fill and rect describe the actual hashed backend. We do not assume
        # 114 or a framework default without inspecting the matching source.
        size,stride=data['image_size'],data['model_stride']
        if (type(size) is not int or type(stride) is not int or
                not 1<=stride<=size<=8192 or size%stride):
            raise ModelDependencyError('actual image_size and model_stride required; align to that stride')
        if type(data['confidence']) not in (int,float) or data['confidence']!=0.65:
            raise ModelDependencyError('source-proven confidence must remain 0.65')
        if (type(data['iou']) not in (int,float) or not math.isfinite(data['iou']) or not 0<data['iou']<1 or
                type(data['max_detections']) is not int or not 1<=data['max_detections']<=100000):
            raise ModelDependencyError('actual NMS IoU/max_detections required; no guessed defaults')
        sources=data.get('sources')
        if type(sources) is not dict:
            raise ModelDependencyError('names YAML and source-contract provenance hashes required')
        actual_sha256(sources.get('names_sha256'),'sources.names_sha256')
        actual_sha256(sources.get('source_contract_sha256'),'sources.source_contract_sha256')
        result = cls(actual_text(data['model_id'],'model_id'), Path(actual_text(data['weights'],'weights')),
                     actual_sha256(data['weights_sha256'],'weights_sha256'),
                     tuple(names), versions, Path(actual_text(data['framework_root'],'framework_root')),
                     data['framework_files'],size,stride,0.65,float(data['iou']),data['max_detections'],
                     contract,source,target)
        if type(result.framework_files) is not dict or not result.framework_files:
            raise ModelDependencyError('actual audited framework file inventory required')
        for filename,digest in result.framework_files.items():
            if (not isinstance(filename,str) or not filename or '\\' in filename or
                    filename.startswith('/') or '..' in filename.split('/') or ':' in filename):
                raise ModelDependencyError('framework inventory requires relative file paths')
            actual_sha256(digest,'framework '+filename)
        return result

    def check_files(self):
        try:
            if not self.weights.is_file() or sha256_file(self.weights)!=self.weights_sha256:
                raise ModelDependencyError('model weights missing or SHA-256 mismatch: '+str(self.weights))
            root = self.framework_root.resolve()
            for name, expected in self.framework_files.items():
                path = (root/name).resolve()
                if root not in path.parents or not path.is_file() or sha256_file(path) != expected:
                    raise ModelDependencyError('audited backend source missing or mismatched: '+name)
        except OSError as exc:
            raise ModelDependencyError('model/backend artifact could not be read') from exc
