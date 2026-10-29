import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from preview_publisher import ArmObserver, PreviewPublisher, observe_sdk


class Clock:
    def __init__(self): self.now = 100.
    def __call__(self): return self.now


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.clock = Clock()
        self.snapshot = dict(frame='frame-1', sequence=1, frame_at=100., camera_error=None)
        self.encode = Mock(return_value=b'JPEG-1')
        self.publisher = PreviewPublisher(self.directory, lambda: dict(self.snapshot),
            pid=123, session_started_at=99., encode=self.encode, clock=self.clock)
        self.publisher.active = True

    def metadata(self):
        return json.loads((self.directory/'live.json').read_text(encoding='utf-8'))

    def test_new_generation_has_no_live_image_before_first_frame(self):
        (self.directory/'latest.jpg').write_bytes(b'OLD-SESSION')
        (self.directory/'live.json').write_text('{"pid":1,"camera_live":true}')
        with patch('preview_publisher.threading.Thread'):
            self.assertTrue(self.publisher.start())
        self.assertFalse((self.directory/'latest.jpg').exists())
        metadata = self.metadata()
        self.assertEqual(metadata['pid'], 123)
        self.assertEqual(metadata['session_started_at'], 99.)
        self.assertFalse(metadata['camera_live'])
        self.assertIsNone(metadata['frame_at'])

    def test_frame_and_json_use_atomic_replace_with_generation(self):
        replaces = []
        native_replace = Path.replace
        def replace(path, target):
            replaces.append((path.name, target.name, path.read_bytes()))
            return native_replace(path, target)
        with patch('preview_publisher.Path.replace', replace):
            self.assertTrue(self.publisher.publish_once())
        self.assertEqual([item[1] for item in replaces], ['latest.jpg', 'live.json'])
        self.assertTrue(all(item[0].endswith('.123.tmp') for item in replaces))
        self.assertEqual((self.directory/'latest.jpg').read_bytes(), b'JPEG-1')
        metadata = self.metadata()
        self.assertTrue(metadata['camera_live'])
        self.assertEqual(metadata['image_sequence'], 1)
        self.assertEqual(metadata['frame_at'], 100.)
        self.assertEqual(metadata['session_started_at'], 99.)

    def test_stale_frame_is_marked_offline_and_not_reencoded(self):
        self.publisher.publish_once()
        self.clock.now = 102.
        self.publisher.publish_once()
        self.assertFalse(self.metadata()['camera_live'])
        self.assertEqual(self.metadata()['frame_at'], 100.)
        self.encode.assert_called_once_with('frame-1')

    def test_camera_error_never_appears_live(self):
        self.snapshot['camera_error'] = 'USB camera unplugged'
        self.publisher.publish_once()
        self.assertFalse(self.metadata()['camera_live'])
        self.assertEqual(self.metadata()['camera_error'], 'USB camera unplugged')
        self.encode.assert_not_called()

    def test_encoder_failure_is_contained_and_can_recover(self):
        self.encode.side_effect = RuntimeError('encoder unavailable')
        self.assertFalse(self.publisher.publish_once())
        self.assertIn('encoder unavailable', self.metadata()['preview_error'])
        self.assertFalse(self.metadata()['camera_live'])
        self.encode.side_effect = None
        self.assertTrue(self.publisher.publish_once())
        self.assertIsNone(self.metadata()['preview_error'])
        self.assertTrue(self.metadata()['camera_live'])

    def test_filesystem_failure_preserves_last_complete_metadata(self):
        self.publisher.publish_once()
        before = (self.directory/'live.json').read_bytes()
        self.snapshot.update(sequence=2, frame_at=101.)
        self.clock.now = 101.
        with patch('preview_publisher.Path.replace', side_effect=OSError('read only')):
            self.assertFalse(self.publisher.publish_once())
        self.assertEqual((self.directory/'live.json').read_bytes(), before)
        self.assertIn('read only', self.publisher.preview_error)

    def test_snapshot_failure_does_not_escape_or_accumulate_unbounded_errors(self):
        self.publisher.camera_snapshot = Mock(side_effect=RuntimeError('x'*5000))
        for _ in range(10): self.assertFalse(self.publisher.publish_once())
        self.assertLessEqual(len(self.publisher.preview_error), 1000)
        self.assertFalse(self.metadata()['camera_live'])

    def test_close_marks_inactive(self):
        self.publisher.publish_once()
        self.publisher.close()
        self.assertFalse(self.metadata()['active'])
        self.assertFalse(self.metadata()['camera_live'])

    def test_control_frame_cursor_is_not_used_by_preview_method(self):
        source = (Path(__file__).resolve().parents[2]/'robot/dofbot/standalone_runtime.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        method = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef) and node.name == 'preview_snapshot')
        attributes = {node.attr for node in ast.walk(method) if isinstance(node, ast.Attribute)}
        self.assertNotIn('get_frame', attributes)
        self.assertNotIn('consumed', attributes)
        self.assertNotIn('VideoCapture', attributes)
        self.assertIn('copy', attributes)


class FakeArm:
    def __init__(self): self.sent = 0; self.calls = []
    def Arm_serial_servo_write6_array(self, joints, duration):
        self.calls.append(('array', joints, duration)); self.sent += 1
        return 'array-result'
    def Arm_serial_servo_write(self, servo, angle, duration):
        self.calls.append(('single', servo, angle, duration)); self.sent += 1
        return 'single-result'


class ArmObserverTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.observer = ArmObserver(self.clock)
        self.arm = FakeArm()
        observe_sdk(self.arm, self.observer, lambda: self.arm.sent)
        self.observer.begin('01', 135)

    def array(self, joints, ms):
        self.clock.now += .01
        self.assertEqual(self.arm.Arm_serial_servo_write6_array(joints, ms), 'array-result')

    def joint(self, servo, angle, ms):
        self.clock.now += .01
        self.assertEqual(self.arm.Arm_serial_servo_write(servo, angle, ms), 'single-result')

    def test_observed_official_sequence_distinguishes_both_open_commands(self):
        high = [90, 80, 50, 50, 265, 135]
        self.array(high, 1000)
        self.joint(6, 30, 500)
        self.assertEqual(self.observer.snapshot()['phase'], 'grasping')
        self.array([90, 40, 30, 72, 265, 30], 500)
        self.joint(6, 135, 500)
        self.array(high, 1000)
        self.assertEqual(self.observer.snapshot()['phase'], 'transferring')
        self.joint(1, 27, 500)
        self.array([27, 110, 0, 40, 265, 135], 1000)
        self.joint(6, 30, 500)
        self.assertEqual(self.observer.snapshot()['phase'], 'releasing')
        self.array([27, 80, 50, 50, 265, 30], 1000)
        self.array([90, 90, 15, 20, 90, 30], 1000)
        self.observer.finish()
        self.assertEqual(len(self.arm.calls), 10)
        self.assertEqual(self.observer.snapshot()['phase'], 'returning')
        self.observer.reconcile({'state': 'grasping', 'busy': True, 'events': [{'at': 105.}]})
        self.assertEqual(self.observer.snapshot()['phase'], 'returning')
        self.observer.reconcile({'state': 'waiting_wake', 'busy': False, 'events': [{'at': 106.}]})
        self.assertEqual(self.observer.snapshot()['phase'], 'idle')

    def test_no_successful_serial_write_means_no_stage_advancement(self):
        arm = FakeArm()
        observe_sdk(arm, self.observer, lambda: 0)
        arm.Arm_serial_servo_write6_array([90, 80, 50, 50, 265, 135], 1000)
        self.assertEqual(self.observer.index, 0)
        self.assertEqual(len(arm.calls), 1)

    def test_observer_failure_does_not_affect_original_call_or_result(self):
        self.observer.observe = Mock(side_effect=RuntimeError('display failed'))
        self.array([90, 80, 50, 50, 265, 135], 1000)
        self.assertEqual(len(self.arm.calls), 1)
        self.assertIn('display failed', self.observer.error)

    def test_counter_failure_does_not_skip_original_command(self):
        arm = FakeArm()
        observe_sdk(arm, self.observer, Mock(side_effect=RuntimeError('display counter failed')))
        self.assertEqual(arm.Arm_serial_servo_write(6, 30, 500), 'single-result')
        self.assertEqual(len(arm.calls), 1)

    def test_original_error_is_preserved_and_never_retried(self):
        arm = FakeArm()
        original = Mock(side_effect=OSError('serial failed'))
        arm.Arm_serial_servo_write = original
        observe_sdk(arm, self.observer, lambda: 0)
        with self.assertRaisesRegex(OSError, 'serial failed'):
            arm.Arm_serial_servo_write(6, 30, 500)
        original.assert_called_once_with(6, 30, 500)
        self.assertEqual(self.observer.index, 0)

    def test_unknown_sequence_falls_back_without_guessing(self):
        self.joint(6, 30, 500)
        self.assertEqual(self.observer.snapshot()['phase'], 'grasping')
        self.assertEqual(self.observer.snapshot()['evidence'], 'unrecognized_sequence_coarse_only')


if __name__ == '__main__':
    unittest.main()
