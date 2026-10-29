"""Package Z19 audio capture, offline Vosk wheels and model assets.

Command recognition lives in fpga/color_locator/host/voice_color.py. This
dependency package contains no controller, command-line service or FPGA loader.
"""
from __future__ import annotations

import argparse
import email.parser
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--model-assets', type=Path, required=True)
    parser.add_argument('--wheels', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    model = args.model_assets / 'vosk-model-small-cn-0.22'
    if not all((model / name).is_file() for name in ('am/final.mdl', 'conf/mfcc.conf')):
        raise RuntimeError('Chinese model files missing')
    wheels = sorted(args.wheels.glob('*.whl'))
    if not wheels or not any(p.name.startswith('vosk-0.3.45-') and 'aarch64' in p.name for p in wheels):
        raise RuntimeError('AArch64 Vosk wheel missing')
    for wheel in wheels:
        if not (wheel.name.endswith('-none-any.whl') or 'aarch64' in wheel.name):
            raise RuntimeError('Non-board wheel in package: ' + wheel.name)
    wheel_metadata = {}
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            metadata_names = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
            if len(metadata_names) != 1:
                raise RuntimeError('Missing/ambiguous wheel metadata: ' + wheel.name)
            metadata = email.parser.Parser().parsestr(archive.read(metadata_names[0]).decode('utf-8'))
            name = metadata['Name'].lower().replace('_', '-')
            if name in wheel_metadata:
                raise RuntimeError('Duplicate package versions: ' + name)
            native_files = []
            for member in archive.namelist():
                if member.endswith('.so'):
                    header = archive.read(member)[:64]
                    if (header[:6] != b'\x7fELF\x02\x01'
                            or int.from_bytes(header[18:20], 'little') != 183):
                        raise RuntimeError('Not a Linux AArch64 ELF library: ' + member)
                    native_files.append(member)
            wheel_metadata[name] = dict(version=metadata['Version'],
                                        requires_python=metadata['Requires-Python'],
                                        file=wheel.name, native_aarch64=native_files,
                                        sha256=hashlib.sha256(wheel.read_bytes()).hexdigest())
    required = {'vosk', 'cffi', 'pycparser', 'requests', 'tqdm', 'srt', 'websockets',
                'charset-normalizer', 'idna', 'urllib3', 'certifi', 'pip', 'setuptools', 'wheel'}
    if not required <= set(wheel_metadata):
        raise RuntimeError('Offline dependency set incomplete: ' + str(required - set(wheel_metadata)))
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    files = [Path('host/app/__init__.py'), Path('host/app/voice/__init__.py'),
             Path('host/app/voice/audio.py'), Path('host/requirements-voice.txt'),
             Path('docs/voice/USB_MICROPHONE.md')]
    for relative in files:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / relative, target)
    shutil.copytree(model, root / 'host/models' / model.name)
    shutil.copyfile(args.model_assets / 'model_provenance.json', root / 'model_provenance.json')
    (root / 'wheels').mkdir()
    for wheel in wheels:
        shutil.copyfile(wheel, root / 'wheels' / wheel.name)
    with (root / 'requirements-voice.lock').open('x', encoding='utf-8') as out:
        for name, item in sorted(wheel_metadata.items()):
            out.write('%s==%s --hash=sha256:%s\n' % (name, item['version'], item['sha256']))
    artifacts = {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in root.rglob('*') if p.is_file()}
    with (root / 'manifest.json').open('x', encoding='utf-8') as out:
        json.dump(dict(profile='z19-audio-assets-v2', target='aarch64-linux-python3.7',
                       hardware='Waveshare USB TO AUDIO', board_validation='pending',
                       recognition_accuracy='not_measured', control='not_connected',
                       wheels=wheel_metadata, sha256=artifacts), out, indent=2)
    print('VOICE_PACKAGE_CREATED: ' + str(root))


if __name__ == '__main__':
    main()
