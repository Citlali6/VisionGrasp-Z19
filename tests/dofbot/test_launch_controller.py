from contextlib import nullcontext
from pathlib import Path
import json
import os
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from launch_controller import Launcher, LaunchError, SINK


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.messages = []
        self.launcher = Launcher(self.root, clock=lambda: 100., sleep=lambda seconds: None,
                                 report=self.messages.append)
        self.launcher.records.mkdir()
        self.launcher.locked = lambda: nullcontext()
        self.identity = dict(pid=123, start_ticks=8000, start_epoch=80., boot_id='boot-a',
            command=['/usr/bin/python3', '-B', str(self.root/'standalone_runtime.py'), '--execute'])
        self.launcher.identity = Mock(return_value=dict(self.identity))
        self.launcher.runtime_processes = Mock(return_value=[])

    def write(self, name, value):
        (self.launcher.records/name).write_text(json.dumps(value), encoding='utf-8')

    def ready(self, *, pid=123, started=90., busy=False, error=None):
        boot = dict(pid=pid, started_at=started, state='ready_for_standalone_voice')
        status = dict(state='fault' if error else 'waiting_wake', busy=busy, error=error,
            events=[{'event': 'ready', 'at': 91.}, {'event': 'serial_open', 'at': 92.}])
        self.write('bootstrap.json', boot)
        self.write('status.json', status)
        return dict(process=dict(self.identity), boot=boot, status=status)

    def test_existing_ready_start_is_idempotent(self):
        self.ready()
        self.launcher.preflight = Mock()
        with patch('launch_controller.subprocess.Popen') as spawn:
            current = self.launcher.start()
        spawn.assert_not_called()
        self.launcher.preflight.assert_not_called()
        self.assertEqual(current['process']['pid'], 123)
        self.assertTrue(any('无需手机' in message for message in self.messages))

    def test_running_fault_is_never_reported_ready_or_restarted(self):
        self.ready(error='speech USB missing')
        with patch('launch_controller.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(LaunchError, '故障状态'):
                self.launcher.start()
        spawn.assert_not_called()

    def test_pid_reuse_rejected_even_if_command_matches(self):
        self.ready()
        changed = dict(self.identity, start_epoch=95., start_ticks=9500)
        self.launcher.identity.return_value = changed
        self.assertIsNone(self.launcher.current())

    def test_start_ticks_and_boot_id_checked_against_manifest(self):
        self.ready()
        self.write('launcher.json', dict(pid=123, start_ticks=7999, boot_id='boot-a', requested_at=85))
        self.assertIsNone(self.launcher.current())
        self.write('launcher.json', dict(pid=123, start_ticks=8000, boot_id='old-boot', requested_at=85))
        self.assertIsNone(self.launcher.current())

    def test_unknown_matching_runtime_is_not_duplicated(self):
        self.launcher.current = Mock(return_value=None)
        self.launcher.runtime_processes.return_value = [self.identity]
        with patch('launch_controller.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(LaunchError, '不会重复启动'):
                self.launcher.start()
        spawn.assert_not_called()

    def test_timed_out_owned_wrapper_cannot_be_started_twice(self):
        self.write('launcher.json', self.manifest())
        self.launcher.identity.return_value = dict(self.identity,
            command=['/bin/bash', str(self.root/'run_runtime.sh')])
        self.launcher.preflight = Mock()
        with patch('launch_controller.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(LaunchError, '上次等待超时'):
                self.launcher.start()
        spawn.assert_not_called()
        self.launcher.preflight.assert_not_called()

    def test_owned_wrapper_status_is_starting_not_ready(self):
        self.write('launcher.json', self.manifest())
        self.launcher.identity.return_value = dict(self.identity,
            command=['/bin/bash', str(self.root/'run_runtime.sh')])
        status = self.launcher.status()
        self.assertTrue(status['starting'])
        self.assertTrue(any('尚未确认就绪' in message for message in self.messages))
        self.launcher._signal_owned = Mock()
        with self.assertRaisesRegex(LaunchError, '启动准备阶段'):
            self.launcher.stop()
        self.launcher._signal_owned.assert_not_called()

    def test_wrapper_pid_reuse_does_not_establish_ownership(self):
        self.write('launcher.json', self.manifest())
        self.launcher.identity.return_value = dict(self.identity, start_ticks=9000,
            command=['/bin/bash', str(self.root/'run_runtime.sh')])
        self.assertIsNone(self.launcher.starting_process())

    def test_missing_device_fails_without_launch(self):
        with patch('launch_controller.Path.exists', return_value=False), \
             patch('launch_controller.subprocess.run') as command:
            with self.assertRaisesRegex(LaunchError, '设备未接入虚拟机'):
                self.launcher.preflight()
        command.assert_not_called()

    def test_preflight_checks_owners_usb_sink_and_pulse_backend(self):
        self.launcher.environment = lambda: {'PULSE_SINK': SINK}
        results = [subprocess.CompletedProcess([], 1, '', '') for _ in range(3)]
        results += [subprocess.CompletedProcess([], 0, '1 '+SINK+' module format SUSPENDED\n', ''),
                    subprocess.CompletedProcess([], 0, 'pulse output Output audio using PulseAudio Server\n', '')]
        with patch('launch_controller.Path.exists', return_value=True), \
             patch('launch_controller.Path.is_file', return_value=True), \
             patch('launch_controller.shutil.which', side_effect=lambda name: '/usr/bin/'+name), \
             patch('launch_controller.subprocess.run', side_effect=results) as command:
            self.launcher.preflight()
        self.assertEqual(command.call_count, 5)
        self.assertEqual(command.call_args.args[0], ['mpg123', '--list-modules'])

    def test_device_owner_is_not_killed_or_ignored(self):
        with patch('launch_controller.Path.exists', return_value=True), \
             patch('launch_controller.Path.is_file', return_value=True), \
             patch('launch_controller.shutil.which', return_value='/usr/bin/tool'), \
             patch('launch_controller.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '456', '')):
            with self.assertRaisesRegex(LaunchError, '其他程序占用'):
                self.launcher.preflight()

    def manifest(self):
        return dict(pid=123, requested_at=89., start_ticks=8000, boot_id='boot-a')

    def test_new_ready_requires_matching_pid_and_new_session_events(self):
        self.ready()
        process = Mock(pid=123)
        process.poll.return_value = None
        current = self.launcher.wait_ready(process, self.manifest(), timeout=1)
        self.assertEqual(current['process']['pid'], 123)
        saved = json.loads((self.launcher.records/'launcher.json').read_text())
        self.assertEqual(saved['bootstrap_started_at'], 90.)
        self.assertEqual(saved['ready_at'], 100.)

    def test_old_status_cannot_confirm_new_start(self):
        self.ready(started=95.)
        process = Mock(pid=123)
        process.poll.return_value = None
        with patch('launch_controller.time.monotonic', side_effect=[0., 0., 2.]):
            with self.assertRaisesRegex(LaunchError, '未确认新进程就绪'):
                self.launcher.wait_ready(process, self.manifest(), timeout=1)
        self.assertFalse((self.launcher.records/'launcher.json').exists())

    def test_bootstrap_from_other_pid_cannot_confirm_new_start(self):
        self.ready(pid=999)
        process = Mock(pid=123)
        process.poll.return_value = None
        with patch('launch_controller.time.monotonic', side_effect=[0., 0., 2.]):
            with self.assertRaises(LaunchError):
                self.launcher.wait_ready(process, self.manifest(), timeout=1)

    def test_child_exit_is_failure_not_readiness(self):
        self.ready()
        process = Mock(pid=123, returncode=1)
        process.poll.return_value = 1
        with self.assertRaisesRegex(LaunchError, '启动进程已退出'):
            self.launcher.wait_ready(process, self.manifest(), timeout=1)

    def test_busy_stop_never_sends_signal(self):
        self.ready(busy=True)
        self.launcher._signal_owned = Mock()
        with self.assertRaisesRegex(LaunchError, '等本轮完成'):
            self.launcher.stop()
        self.launcher._signal_owned.assert_not_called()

    def test_stop_rechecks_identity_before_signal(self):
        self.launcher._same_process = Mock(return_value=False)
        with patch('launch_controller.os.pidfd_open', return_value=55, create=True), \
             patch('launch_controller.signal.pidfd_send_signal', create=True) as send, \
             patch('launch_controller.os.close'):
            with self.assertRaisesRegex(LaunchError, '身份已变化'):
                self.launcher._signal_owned(self.identity)
        send.assert_not_called()

    def test_stop_uses_sigterm_only_for_verified_pidfd(self):
        self.launcher._same_process = Mock(return_value=True)
        with patch('launch_controller.os.pidfd_open', return_value=55, create=True), \
             patch('launch_controller.signal.pidfd_send_signal', create=True) as send, \
             patch('launch_controller.os.close'):
            self.launcher._signal_owned(self.identity)
        send.assert_called_once_with(55, signal.SIGTERM)

    def test_idle_stop_waits_and_never_force_kills(self):
        self.ready()
        self.launcher._signal_owned = Mock()
        self.launcher._same_process = Mock(return_value=False)
        self.launcher.stop()
        self.launcher._signal_owned.assert_called_once()
        self.assertTrue(any('已停止' in message for message in self.messages))

    def test_archive_preserves_old_images_and_keeps_ik_log(self):
        names = ('bootstrap.json', 'status.json', 'arm-tx.jsonl', 'runtime.log', 'cycle-001-detection.jpg')
        for name in names:
            (self.launcher.records/name).write_bytes(name.encode())
        (self.launcher.records/'kinematics.log').write_text('keep live IK log')
        self.launcher.archive_session()
        archives = list((self.launcher.records/'archive').iterdir())
        self.assertEqual(len(archives), 1)
        for name in names:
            self.assertEqual((archives[0]/name).read_bytes(), name.encode())
            self.assertFalse((self.launcher.records/name).exists())
        self.assertTrue((self.launcher.records/'kinematics.log').exists())

    def test_start_spawns_background_shell_and_waits_new_identity(self):
        self.launcher.current = Mock(return_value=None)
        self.launcher.preflight = Mock(return_value={'TEST': '1'})
        self.launcher.wait_ready = Mock(return_value={'ready': True})
        process = Mock(pid=123)
        with patch('launch_controller.subprocess.Popen', return_value=process) as spawn:
            result = self.launcher.start()
        self.assertEqual(result, {'ready': True})
        self.assertEqual(spawn.call_args.args[0], ['/bin/bash', str(self.root/'run_runtime.sh')])
        self.assertTrue(spawn.call_args.kwargs['start_new_session'])
        manifest = self.launcher.wait_ready.call_args.args[1]
        self.assertEqual(manifest['pid'], 123)
        self.assertEqual(manifest['start_ticks'], 8000)


if __name__ == '__main__':
    unittest.main()
