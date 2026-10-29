import subprocess
import unittest
from unittest.mock import Mock, patch

from standalone_voice import BlockingPlayer, Session


class Clock:
    def __init__(self): self.now = 100.
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.calls, self.saves = [], []
        self.msg = {'Zip_top_can': (.2, .01)}
        self.session = Session(prepare=lambda: self.calls.append('prepare'),
            detect=self.detect, play=self.play,
            grasp=lambda category: self.calls.append(('grasp', category)),
            enable_motion=True, clock=self.clock, sleep=self.clock.sleep,
            save=self.saves.append, clear_input=lambda: self.calls.append('clear_input'))

    def detect(self):
        self.calls.append('detect')
        self.clock.sleep(.1)
        return 'frame', dict(self.msg)

    def play(self, number, language):
        self.calls.append(('audio_begin', number, language))
        self.clock.sleep(.2)
        self.calls.append(('audio_end', number, language))

    def start(self):
        self.session.handle(1, 0)
        return self.session.handle(0, 108)

    def test_strict_wake_start_detection_audio_finish_grasp_order(self):
        self.assertEqual(self.calls, [])
        self.session.handle(1, 0)
        self.assertNotIn('prepare', self.calls)
        self.assertNotIn('detect', self.calls)
        self.assertTrue(self.session.handle(0, 108))
        expected = [('audio_begin', 0, 'cn'), ('audio_end', 0, 'cn'), 'clear_input',
                    'prepare', 'detect', 'detect', 'detect',
                    ('audio_begin', 94, 'cn'), ('audio_end', 94, 'cn'),
                    ('grasp', '01'), 'clear_input']
        self.assertEqual(self.calls, expected)
        status = self.session.snapshot()
        self.assertEqual(status['state'], 'waiting_wake')
        self.assertFalse(status['busy'])
        self.assertEqual(status['labelChinese'], '易拉罐')
        self.assertEqual(status['categoryChinese'], '可回收垃圾')
        self.assertFalse(status['physical_grasp_verified'])
        self.assertFalse(status['phone_required'])

    def test_no_start_without_wake_and_nonstart_commands_ignored(self):
        self.session.handle(0, 108)
        self.session.handle(0, 92)
        self.assertEqual(self.calls, [])
        self.session.handle(1, 0)
        for command in (94, 93, 0):
            self.session.handle(0, command)
        self.assertNotIn('prepare', self.calls)
        self.assertNotIn('detect', self.calls)
        self.assertEqual(self.session.cycles, 0)

    def test_real_module_start_sorting_92_alias(self):
        self.session.handle(1, 0, raw='aa550100fb')
        self.assertTrue(self.session.handle(0, 92, raw='aa55005cfb'))
        self.assertEqual(self.session.grasp_calls, 1)
        self.assertEqual(self.session.state, 'waiting_wake')
        self.assertFalse(self.session.handle(0, 92))
        self.assertLess(self.calls.index(('audio_end', 94, 'cn')),
                        self.calls.index(('grasp', '01')))

    def test_every_completed_cycle_requires_a_new_wake_then_start(self):
        self.session.handle(1, 0)
        self.assertTrue(self.session.handle(0, 92))
        self.assertEqual(self.session.grasp_calls, 1)
        self.assertEqual(self.session.state, 'waiting_wake')
        self.assertIsNone(self.session.awake_at)
        # Even within the original 20-second wake window, no start alias may
        # repeat a completed grasp, and no additional detection may occur.
        frames_after_first_cycle = self.calls.count('detect')
        for command in (92, 108, 92, 108):
            self.assertFalse(self.session.handle(0, command))
        self.assertEqual(self.session.grasp_calls, 1)
        self.assertEqual(self.calls.count('detect'), frames_after_first_cycle)
        # A fresh wake only arms the next cycle; the new start is mandatory.
        self.session.handle(1, 0)
        self.assertEqual(self.session.grasp_calls, 1)
        self.assertEqual(self.calls.count('detect'), frames_after_first_cycle)
        self.assertTrue(self.session.handle(0, 108))
        self.assertEqual(self.session.grasp_calls, 2)
        self.assertEqual(self.session.state, 'waiting_wake')
        self.assertIsNone(self.session.awake_at)
        self.assertFalse(self.session.handle(0, 92))
        self.assertEqual(self.session.grasp_calls, 2)

    def test_wake_expires_after_twenty_seconds(self):
        self.session.handle(1, 0)
        self.clock.sleep(21)
        self.assertFalse(self.session.handle(0, 108))
        self.assertNotIn('prepare', self.calls)

    def test_no_target_timeout_does_not_grasp_or_retry(self):
        self.msg = {}
        self.start()
        self.assertEqual(self.session.last_result, 'no_stable_target_timeout')
        self.assertEqual(self.session.grasp_calls, 0)
        self.assertEqual(self.calls.count('prepare'), 1)
        self.assertFalse(self.session.handle(0, 108))
        self.assertEqual(self.calls.count('prepare'), 1)

    def test_one_cycle_consumes_wake_and_stale_queue_generation(self):
        generation = self.session.generation
        self.start()
        self.assertFalse(self.session.handle(1, 0, generation=generation))
        self.assertFalse(self.session.handle(0, 108))
        self.assertEqual(self.session.grasp_calls, 1)
        self.assertEqual(self.session.cycles, 1)

    def test_busy_input_is_ignored_without_rearming(self):
        original = self.session.detect
        def detect():
            self.assertTrue(self.session.busy)
            self.assertFalse(self.session.handle(1, 0))
            self.assertFalse(self.session.handle(0, 108))
            return original()
        self.session.detect = detect
        self.start()
        self.assertEqual(self.session.cycles, 1)
        self.assertIsNone(self.session.awake_at)

    def test_audio_failure_prevents_grasp(self):
        original = self.session.play
        def play(number, language):
            if number != 0: raise RuntimeError('speaker playback failed')
            original(number, language)
        self.session.play = play
        self.start()
        self.assertEqual(self.session.grasp_calls, 0)
        self.assertEqual(self.session.state, 'fault')
        self.assertIn('speaker playback failed', self.session.error)

    def test_wake_audio_failure_prevents_prepare_and_recognition(self):
        self.session.play = Mock(side_effect=RuntimeError('wake audio failed'))
        self.start()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.session.cycles, 0)

    def test_serial_error_during_classification_audio_prevents_grasp(self):
        original = self.session.play
        def play(number, language):
            original(number, language)
            if number: self.session.fail('speech_serial disconnected')
        self.session.play = play
        self.start()
        self.assertEqual(self.session.grasp_calls, 0)
        self.assertEqual(self.session.state, 'fault')

    def test_slow_detection_results_are_never_fresh(self):
        def detect():
            self.clock.sleep(2)
            return 'frame', self.msg
        self.session.detect = detect
        self.start()
        self.assertEqual(self.session.grasp_calls, 0)
        self.assertEqual(self.session.last_result, 'no_stable_target_timeout')

    def test_wrong_label_and_nonfinite_position_never_grasp(self):
        for msg in ({'Unknown': (.2, .01)}, {'Zip_top_can': (float('nan'), .01)}):
            self.setUp()
            self.msg = msg
            self.start()
            self.assertEqual(self.session.grasp_calls, 0)

    def test_stability_resets_on_name_and_position_change(self):
        targets = iter([
            {'Book': (.2, .01)}, {'Syringe': (.2, .01)},
            {'Syringe': (.21, .01)}, {'Syringe': (.21, .01)}, {'Syringe': (.21, .01)}])
        def detect():
            self.clock.sleep(.1)
            return 'frame', next(targets)
        self.session.detect = detect
        self.start()
        self.assertEqual(self.session.recognition_frames, 5)
        self.assertEqual(self.session.category, '04')
        self.assertIn(('audio_end', 98, 'cn'), self.calls)
        self.assertIn(('grasp', '04'), self.calls)

    def test_dry_run_is_default_and_skips_both_motion_callbacks(self):
        self.session = Session(prepare=lambda: self.calls.append('prepare'), detect=self.detect,
            play=self.play, grasp=lambda category: self.calls.append('grasp'),
            clock=self.clock, sleep=self.clock.sleep)
        self.start()
        self.assertNotIn('prepare', self.calls)
        self.assertNotIn('grasp', self.calls)
        self.assertEqual(self.session.last_result, 'dry_run_completed')

    def test_action_error_does_not_retry(self):
        self.session.grasp = Mock(side_effect=OSError('motion failed'))
        self.start()
        self.session.handle(1, 0)
        self.session.handle(0, 108)
        self.session.grasp.assert_called_once_with('01')
        self.assertEqual(self.session.state, 'fault')

    def test_stop_after_prepare_prevents_detection(self):
        self.session.prepare = self.session.request_stop
        self.start()
        self.assertNotIn('detect', self.calls)
        self.assertEqual(self.session.state, 'stopped')

    def test_final_one_second_wait_keeps_busy(self):
        original_sleep = self.session.sleep
        holds = []
        def sleep(seconds):
            if seconds == 1: holds.append(self.session.busy)
            original_sleep(seconds)
        self.session.sleep = sleep
        self.start()
        self.assertEqual(holds, [True])


class PlayerTests(unittest.TestCase):
    def invoke(self, result):
        with patch('standalone_voice.Path.is_file', return_value=True), \
             patch('standalone_voice.os.getuid', return_value=1000, create=True), \
             patch('standalone_voice.subprocess.run', return_value=result) as run:
            BlockingPlayer()(98, 'cn')
        return run

    def test_blocking_success_selects_requested_file(self):
        run = self.invoke(subprocess.CompletedProcess([], 0, b'', b''))
        args = run.call_args.args[0]
        self.assertEqual(args[:4], ['mpg123', '-q', '-o', 'pulse'])
        self.assertTrue(args[-1].endswith('answer98.mp3'))
        self.assertEqual(run.call_args.kwargs['timeout'], 30)

    def test_nonzero_player_exit_raises(self):
        with self.assertRaisesRegex(RuntimeError, 'Audio playback failed'):
            self.invoke(subprocess.CompletedProcess([], 1, b'', b'no sink'))


if __name__ == '__main__':
    unittest.main()
