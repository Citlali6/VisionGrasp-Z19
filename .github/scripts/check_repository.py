"""Check the source release without importing drivers or contacting hardware."""
from pathlib import Path
from urllib.parse import unquote, urlsplit
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ('AmazingHand', 'pc', 'sim', 'fpga/hand_control', 'fpga/mjc1_fpd',
             'docs/migration', 'docs/relaunch_20261020', 'deliverables/mjc1_fpd',
             'deliverables/local_sources', 'start_virtual_hand.bat', 'start_mjc1_observer.bat')
LARGE_ASSETS = {'deliverables/voice_usb/voice_usb_package_20261018_v2.zip'}
TEXT_SUFFIXES = {'.py', '.md', '.json', '.yml', '.yaml', '.toml', '.sh', '.ps1', '.txt'}
FROZEN_README = 'deliverables/dofbot_demo_20261029/payload/README.md'
FROZEN_README_SOURCE = {
    'source_commit': '8a2a6fd544cb6b79e868b8a710dc34b6027c6c8d',
    'source_path': 'robot/dofbot/README.md',
    'source_git_blob': 'b4f6a9d51e0246ad063709516393d4fa27fdff06',
    'sha256': 'f2e2613b3fdc1f93c79b48e22cff861d8bfd311b190c2ec9c4704f457f972c3b',
}


def markdown_prose(text):
    """Remove paired backtick/tilde fences without treating shorter runs as closers."""
    prose, fence = [], None
    for line in text.splitlines(keepends=True):
        match = re.match(r'^ {0,3}(`{3,}|~{3,})([^\r\n]*)[\r\n]*$', line)
        if fence is None:
            if match and not (match[1][0] == '`' and '`' in match[2]):
                fence = match[1]
            else:
                prose.append(line)
                continue
        elif match and match[1] == fence and not match[2].strip():
            fence = None
        # Preserve separation around omitted blocks, including unclosed fences.
        if line.endswith('\n'):
            prose.append('\n')
    return ''.join(prose)


def markdown_link_base(path, errors):
    """Use the original context only for the byte-pinned historical README."""
    if path.relative_to(ROOT).as_posix() != FROZEN_README:
        return path.parent
    try:
        provenance = json.loads((ROOT/'deliverables/dofbot_demo_20261029/provenance.json').read_text(encoding='utf-8'))
        if not isinstance(provenance, dict) or provenance.get('source_commit') != FROZEN_README_SOURCE['source_commit']:
            raise ValueError('source_commit does not match the frozen baseline')
        records = provenance.get('files')
        if not isinstance(records, list):
            raise ValueError('files must be a list')
        matching = [record for record in records if isinstance(record, dict) and record.get('path') == 'payload/README.md']
        if len(matching) != 1:
            raise ValueError('expected exactly one payload/README.md record')
        record = matching[0]
        for key in ('source_path', 'source_git_blob', 'sha256'):
            if record.get(key) != FROZEN_README_SOURCE[key]:
                raise ValueError(key+' does not match the frozen baseline')
        if hashlib.sha256(path.read_bytes()).hexdigest() != FROZEN_README_SOURCE['sha256']:
            raise ValueError('README bytes differ from the frozen SHA-256')
    except (OSError, UnicodeError, ValueError) as error:
        errors.append('Invalid frozen README provenance: '+str(error))
        return None
    return (ROOT/FROZEN_README_SOURCE['source_path']).parent


def check_guard_evidence(errors):
    module = ROOT/'fpga/sort_guard'
    manifest = json.loads((module/'validation/result.json').read_text(encoding='utf-8'))
    evidence = manifest['reproducibility']
    entries = [(module, name, digest) for name, digest in evidence['source_sha256'].items()]
    entries += [(module/'validation', name, record['published_sha256'])
                for name, record in evidence['published_reports'].items()]
    for base, name, expected in entries:
        path = (base/name).resolve()
        if not path.is_relative_to(base.resolve()) or not path.is_file():
            errors.append('Invalid evidence input: '+name)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append('Evidence hash differs from validated input: '+path.relative_to(ROOT).as_posix())


def main():
    errors = []
    names = subprocess.check_output(['git', 'ls-files', '-c', '-o', '--exclude-standard', '-z'],
                                    cwd=ROOT).decode('utf-8').split('\0')
    paths = sorted({ROOT/name for name in names if name and (ROOT/name).is_file()})
    for name in FORBIDDEN:
        if (ROOT/name).exists(): errors.append('Obsolete entry still present: '+name)
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if path.name in ('guest_tool.py', 'sources.zip'):
            errors.append('Local-only dependency/helper included: '+relative)
        if path.stat().st_size > 20*1024*1024 and relative not in LARGE_ASSETS:
            errors.append('Unlisted large asset: '+relative)
        if path.suffix not in TEXT_SUFFIXES: continue
        data = path.read_text(encoding='utf-8-sig')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}', data):
            errors.append('Possible credential material: '+relative)
        if path.suffix != '.md': continue
        link_base = markdown_link_base(path, errors)
        if link_base is None:
            continue
        prose = markdown_prose(data)
        for target in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', prose):
            target = target.strip()
            if target.startswith('<'): target = target.split('>')[0][1:]
            else: target = re.split(r'\s+[\"\']', target)[0]
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith(('#', '//')): continue
            local = unquote(parsed.path)
            if local:
                linked = Path(os.path.abspath(link_base/local))
                if not linked.exists():
                    errors.append('Broken local link: '+relative+' -> '+target)
                elif linked.is_relative_to(ROOT):
                    # Windows ignores case; a public Linux checkout does not.
                    current = ROOT
                    for part in linked.relative_to(ROOT).parts:
                        if part not in {item.name for item in current.iterdir()}:
                            errors.append('Link case mismatch: '+relative+' -> '+target)
                            break
                        current = current/part
    check_guard_evidence(errors)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Repository checks passed: %s files; no hardware accessed.' % len(paths))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
