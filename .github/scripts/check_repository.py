"""Check the source release without importing drivers or contacting hardware."""
from pathlib import Path
from urllib.parse import unquote, urlsplit
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
        prose = re.sub(r'^```[^\n]*\n.*?^```\s*$', '', data, flags=re.M | re.S)
        for target in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', prose):
            target = target.strip()
            if target.startswith('<'): target = target.split('>')[0][1:]
            else: target = re.split(r'\s+[\"\']', target)[0]
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith(('#', '//')): continue
            local = unquote(parsed.path)
            if local:
                linked = Path(os.path.abspath(path.parent/local))
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
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Repository checks passed: %s files; no hardware accessed.' % len(paths))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
