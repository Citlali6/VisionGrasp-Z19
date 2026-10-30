"""Create a real manifest from legally supplied artifacts, without inference.

Future explicit utility; not run for the 2026-10-30 source delivery. A source
contract JSON must be collected from the matching VM/backend, not guessed from
the directory name. Hashing weights does not deserialize their pickle content.
"""
import argparse
import json
from pathlib import Path
from .model_manifest import sha256_file


FRAMEWORK_FILES = ('ultralytics/__init__.py','ultralytics/engine/predictor.py',
                   'ultralytics/models/yolo/detect/predict.py',
                   'ultralytics/data/augment.py','ultralytics/utils/ops.py',
                   'ultralytics/cfg/default.yaml')


def enroll(*, weights, framework_root, names_yaml, source_contract, output):
    import yaml
    weights,framework_root,names_yaml = Path(weights),Path(framework_root),Path(names_yaml)
    contract=json.loads(Path(source_contract).read_text(encoding='utf-8'))
    if contract.get('schema')!='visiongrasp.vm-backend-contract/1':
        raise ValueError('matching VM-derived backend contract required')
    names=yaml.safe_load(names_yaml.read_text(encoding='utf-8'))['names']
    if isinstance(names,dict):
        if set(names)!=set(range(len(names))):
            raise ValueError('class IDs must be contiguous from zero')
        names=[names[i] for i in range(len(names))]
    if not isinstance(names,list) or not names or not all(isinstance(n,str) and n for n in names):
        raise ValueError('actual ordered class names required')
    if contract.get('names_sha256')!=sha256_file(names_yaml):
        raise ValueError('names YAML differs from matching source contract')
    if contract.get('weights_sha256')!=sha256_file(weights):
        raise ValueError('weights differ from matching source contract')
    implementation={name:sha256_file(framework_root/name) for name in FRAMEWORK_FILES}
    if implementation != contract.get('framework_files'):
        raise ValueError('framework source differs from matching source contract')
    manifest=dict(schema='visiongrasp.ps-model-manifest/1',
                  model_id='yahboom-best-sha256-'+contract['weights_sha256'],
                  weights=str(weights.resolve()),weights_sha256=contract['weights_sha256'],
                  names=names,versions=contract['versions'],
                  framework_root=str(framework_root.resolve()),framework_files=implementation,
                  image_size=contract['image_size'],confidence=0.65,iou=contract['iou'],
                  max_detections=contract['max_detections'],
                  preprocess=contract['preprocess'],
                  sources=dict(names_sha256=sha256_file(names_yaml),
                               source_contract_sha256=sha256_file(source_contract)))
    destination=Path(output)
    if destination.exists():
        raise FileExistsError('refusing to overwrite enrolled manifest')
    destination.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('weights','framework-root','names-yaml','source-contract','output'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    enroll(weights=args.weights,framework_root=args.framework_root,names_yaml=args.names_yaml,
           source_contract=args.source_contract,output=args.output)


if __name__=='__main__':
    main()
