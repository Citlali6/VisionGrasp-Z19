from pathlib import Path
from contextlib import redirect_stdout
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

REPOSITORY = Path(__file__).resolve().parents[2]
SOURCE = REPOSITORY/'deliverables/dofbot_demo_20261029/payload'
spec = importlib.util.spec_from_file_location('dofbot_install', REPOSITORY/'robot/dofbot/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.stage = self.root/'stage'
        self.home = self.stage/'home/yahboom'
        self.destination = self.home/'codex_voice_sorting_20261029'
        self.proc = self.root/'proc'
        self.proc.mkdir()

    def install(self, **kwargs):
        return installer.install(staging_root=self.stage, proc=self.proc, **kwargs)

    def test_check_only_never_creates_destination_or_runs_commands(self):
        with patch.object(installer.subprocess, 'run', side_effect=AssertionError('Unexpected command')):
            result = self.install(check_only=True)
        self.assertEqual(result['state'], 'checked')
        self.assertEqual(result['source'], str(SOURCE.resolve()))
        self.assertFalse(self.stage.exists())

    def test_cli_accepts_an_independent_frozen_source_directory(self):
        source = self.root/'independent-frozen-checkout/robot/dofbot'
        source.mkdir(parents=True)
        for name in installer.PAYLOAD_FILES:
            shutil.copyfile(SOURCE/name, source/name)
        output = io.StringIO()
        with patch.object(installer.subprocess, 'run', side_effect=AssertionError('Unexpected command')):
            with redirect_stdout(output):
                code = installer.main(['--source', str(source), '--staging-root', str(self.stage), '--check'])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['state'], 'checked')
        self.assertEqual(result['source'], str(source.resolve()))
        self.assertFalse(self.stage.exists())

    def test_staging_install_writes_only_payload_and_compatible_launchers(self):
        with patch.object(installer.subprocess, 'run', side_effect=AssertionError('Unexpected command')):
            result = self.install()
        self.assertFalse(result['started_runtime'])
        self.assertFalse(result['opened_devices'])
        self.assertFalse(result['changed_volume'])
        self.assertEqual(result['source'], str(SOURCE.resolve()))
        for name in installer.PAYLOAD_FILES:
            self.assertEqual((self.destination/name).read_bytes(), (SOURCE/name).read_bytes())
        start = (self.home/'启动垃圾分拣.sh').read_text(encoding='utf-8')
        self.assertIn('"${1:-start}"', start)
        self.assertIn(str(self.destination/'start.sh'), start)
        entry = (self.home/'Desktop/启动垃圾分拣.desktop').read_text(encoding='utf-8')
        self.assertIn('Name=启动垃圾分拣 · 实时展示', entry)
        self.assertIn('Terminal=true', entry)
        self.assertNotIn('guest_tool', '\n'.join(result['files']))

    def test_verified_source_hashes_are_enforced_before_writes(self):
        source = self.root/'source'
        source.mkdir()
        for name in installer.PAYLOAD_FILES:
            shutil.copyfile(SOURCE/name, source/name)
        (source/'standalone_voice.py').write_text('changed = True\n')
        with self.assertRaisesRegex(installer.InstallError, r'^源码校验失败：standalone_voice\.py$'):
            self.install(source=source)
        self.assertFalse(self.stage.exists())

    def test_manifest_cannot_add_unlisted_paths(self):
        source = self.root/'source'
        source.mkdir()
        manifest = json.loads((SOURCE/'deployment_manifest.json').read_text(encoding='utf-8'))
        manifest['files']['../unrelated.py'] = '0'*64
        (source/'deployment_manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(installer.InstallError, '^源码清单与安装文件列表不一致。$'):
            self.install(source=source)
        self.assertFalse(self.stage.exists())

    def test_active_runtime_is_never_overwritten(self):
        process = self.proc/'123'
        process.mkdir()
        command = '\0'.join(['/usr/bin/python3', '-B', str(self.destination/'standalone_runtime.py'), '--execute'])
        (process/'cmdline').write_bytes(command.encode())
        with self.assertRaisesRegex(installer.InstallError, r'^现有实例仍在运行（PID \[123\]）'):
            self.install()
        self.assertFalse(self.stage.exists())

    def test_active_dashboard_is_never_overwritten(self):
        process = self.proc/'234'
        process.mkdir()
        (process/'cmdline').write_bytes(('/usr/bin/python3\0-B\0'+str(self.destination/'dashboard.py')).encode())
        with self.assertRaisesRegex(installer.InstallError, r'^现有实例仍在运行（PID \[234\]）'):
            self.install()
        self.assertFalse(self.stage.exists())

    def test_unknown_files_survive_and_replaced_files_are_backed_up(self):
        self.destination.mkdir(parents=True)
        (self.destination/'start.sh').write_bytes(b'previous launcher')
        (self.destination/'calibration.json').write_bytes(b'preserve me')
        result = self.install()
        backup = Path(result['backup'])
        self.assertIn(b'previous launcher', [p.read_bytes() for p in backup.iterdir() if p.is_file()])
        self.assertEqual((self.destination/'calibration.json').read_bytes(), b'preserve me')

    def test_partial_copy_failure_restores_originals(self):
        self.destination.mkdir(parents=True)
        first = self.destination/'standalone_runtime.py'
        first.write_bytes(b'old runtime')
        original = installer.atomic_write
        calls = []
        def injected(path, data, mode):
            calls.append(path)
            if len(calls) == 2:
                raise OSError('simulated write failure')
            return original(path, data, mode)
        with patch.object(installer, 'atomic_write', side_effect=injected):
            with self.assertRaisesRegex(OSError, 'simulated'):
                self.install()
        self.assertEqual(first.read_bytes(), b'old runtime')
        self.assertFalse((self.destination/'standalone_voice.py').exists())

    def test_existing_directory_is_not_replaced_with_script(self):
        (self.destination/'start.sh').mkdir(parents=True)
        with self.assertRaisesRegex(installer.InstallError, '不是普通文件'):
            self.install()
        self.assertTrue((self.destination/'start.sh').is_dir())


if __name__ == '__main__':
    unittest.main()
