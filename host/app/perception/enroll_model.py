"""Create a real manifest from legally supplied artifacts, without inference.

Future explicit utility; not run for the 2026-10-30 source delivery. A source
contract JSON must be collected from the matching VM/backend, not guessed from
the directory name. Hashing weights does not deserialize their pickle content.
"""
import argparse
import json
from pathlib import Path
from .model_manifest import ModelDependencyError, ModelManifest, actual_sha256, sha256_file


def enroll(*, weights, framework_root, names_yaml, source_contract, output):
    try:
        return _enroll(weights=weights,framework_root=framework_root,names_yaml=names_yaml,
                       source_contract=source_contract,output=output)
    except ModelDependencyError:
        raise
    except (OSError,ValueError,TypeError,KeyError,ImportError) as exc:
        raise ModelDependencyError('model enrollment dependency/contract is missing, unreadable or malformed') from exc


def _enroll(*, weights, framework_root, names_yaml, source_contract, output):
    import yaml
    weights,framework_root,names_yaml = Path(weights),Path(framework_root),Path(names_yaml)
    contract=json.loads(Path(source_contract).read_text(encoding='utf-8'))
    if type(contract) is not dict or contract.get('schema')!='visiongrasp.vm-backend-contract/1':
        raise ModelDependencyError('matching VM reference and AArch64 target contract required')
    try:
        document=yaml.safe_load(names_yaml.read_text(encoding='utf-8'))
    except yaml.YAMLError as exc:
        raise ModelDependencyError('matching names YAML is malformed') from exc
    if type(document) is not dict:
        raise ModelDependencyError('matching names YAML must be an object')
    names=document.get('names')
    if isinstance(names,dict):
        if any(type(k) is not int for k in names) or set(names)!=set(range(len(names))):
            raise ModelDependencyError('class IDs must be contiguous integers from zero')
        names=[names[i] for i in range(len(names))]
    if not isinstance(names,list) or not names or not all(isinstance(n,str) and n for n in names):
        raise ModelDependencyError('actual ordered class names required')
    if contract.get('names_sha256')!=sha256_file(names_yaml):
        raise ModelDependencyError('names YAML differs from matching source contract')
    if contract.get('weights_sha256')!=sha256_file(weights):
        raise ModelDependencyError('weights differ from matching source contract')
    if names!=contract.get('names'):
        raise ModelDependencyError('ordered names differ from source weight/YAML contract')
    implementation=contract.get('framework_files')
    # This exact audited inventory is also checked by the runtime reader. No
    # guessed five/six-file list tied to a particular Ultralytics release.
    if type(implementation) is not dict or not implementation:
        raise ModelDependencyError('actual audited framework file inventory required')
    root=framework_root.resolve()
    for name,expected in implementation.items():
        if not isinstance(name,str):
            raise ModelDependencyError('framework path must be a relative string')
        path=(root/name).resolve()
        if root not in path.parents or sha256_file(path)!=actual_sha256(expected,'framework '+name):
            raise ModelDependencyError('framework source differs from matching contract: '+name)
    manifest=dict(schema='visiongrasp.ps-model-manifest/1',
                  model_id='yahboom-best-sha256-'+contract['weights_sha256'],
                  weights=str(weights.resolve()),weights_sha256=contract['weights_sha256'],
                  names=names,versions=contract['target_environment']['versions'],
                  framework_root=str(framework_root.resolve()),framework_files=implementation,
                  image_size=contract['image_size'],model_stride=contract['model_stride'],
                  confidence=contract['confidence'],iou=contract['iou'],
                  max_detections=contract['max_detections'],
                  preprocess=contract['preprocess'],
                  source_environment=contract['source_environment'],
                  target_environment=contract['target_environment'],
                  compatibility_notes=contract['compatibility_notes'],
                  sources=dict(names_sha256=sha256_file(names_yaml),
                               source_contract_sha256=sha256_file(source_contract)))
    # Reject an inconsistent contract before creating a deployment document.
    ModelManifest.from_data(manifest)
    with Path(output).open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('weights','framework-root','names-yaml','source-contract','output'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    enroll(weights=args.weights,framework_root=args.framework_root,names_yaml=args.names_yaml,
           source_contract=args.source_contract,output=args.output)


if __name__=='__main__':
    main()
