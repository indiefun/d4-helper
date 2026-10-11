import ctypes
import unittest
from unittest.mock import patch

import right_hold_toggle as app


class FakeUser32:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls = []

    def SendInput(self, count, inputs, _size):
        array = ctypes.cast(inputs, ctypes.POINTER(app.INPUT * count)).contents
        flags = [
            item.union.mi.dwFlags if item.type == app.INPUT_MOUSE else item.union.ki.dwFlags
            for item in array
        ]
        self.calls.append(flags)
        return self.results.pop(0) if self.results else count


class InputSafetyTests(unittest.TestCase):
    def setUp(self):
        with app.PENDING_RELEASES_LOCK:
            app.PENDING_RELEASES.clear()

    def tearDown(self):
        with app.PENDING_RELEASES_LOCK:
            app.PENDING_RELEASES.clear()

    def test_macro_interval_allows_one_millisecond(self):
        self.assertEqual(app.parse_interval_ms(1, "快速连击"), 1)
        macro = app.MacroConfig(True, "测试", "f1", app.ACTION_PRESS_CYCLE, ["f"], 0, "test")
        self.assertEqual(app.normalize_macros([macro])[0].interval_ms, 1)

    def test_native_kernel_accepts_macro_definition(self):
        kernel = app.FastInputKernel()
        self.addCleanup(kernel.close)
        if not kernel.available:
            self.skipTest("native kernel DLL is not built")
        macro = app.MacroConfig(True, "测试", "f1", app.ACTION_PRESS_CYCLE, ["f"], 1, "native")
        kernel.configure([macro])
        self.assertEqual(kernel.slots, {"native": 0})

    def test_empty_cleanup_does_not_emit_mouse_events(self):
        engine = app.MacroEngine(app.Config(macros=[]))
        fake = FakeUser32()
        with patch.object(app, "user32", fake):
            engine.release_all_inputs()
        self.assertEqual(fake.calls, [])

    def test_click_uses_atomic_down_up_pair(self):
        fake = FakeUser32()
        with patch.object(app, "user32", fake):
            app.click_right()
        self.assertEqual(fake.calls, [[app.MOUSEEVENTF_RIGHTDOWN, app.MOUSEEVENTF_RIGHTUP]])

    def test_zero_inserted_click_does_not_emit_unpaired_up(self):
        fake = FakeUser32([0])
        with patch.object(app, "user32", fake):
            with self.assertRaises(OSError):
                app.click_right()
        self.assertEqual(fake.calls, [[app.MOUSEEVENTF_RIGHTDOWN, app.MOUSEEVENTF_RIGHTUP]])

    def test_one_inserted_click_retries_only_matching_up(self):
        fake = FakeUser32([1, 1])
        with patch.object(app, "user32", fake):
            with self.assertRaises(OSError):
                app.click_right()
        self.assertEqual(
            fake.calls,
            [
                [app.MOUSEEVENTF_RIGHTDOWN, app.MOUSEEVENTF_RIGHTUP],
                [app.MOUSEEVENTF_RIGHTUP],
            ],
        )

    def test_failed_click_recovery_is_tracked_for_later_retry(self):
        fake = FakeUser32([1, 0, 1])
        with patch.object(app, "user32", fake):
            with self.assertRaises(OSError):
                app.click_right()
            self.assertTrue(app.has_pending_releases())
            self.assertTrue(app.retry_pending_releases())

        self.assertFalse(app.has_pending_releases())
        self.assertEqual(
            fake.calls,
            [
                [app.MOUSEEVENTF_RIGHTDOWN, app.MOUSEEVENTF_RIGHTUP],
                [app.MOUSEEVENTF_RIGHTUP],
                [app.MOUSEEVENTF_RIGHTUP],
            ],
        )

    def test_failed_key_recovery_is_tracked_for_later_retry(self):
        fake = FakeUser32([1, 0, 1])
        with patch.object(app, "user32", fake):
            with self.assertRaises(OSError):
                app.tap_key(app.KEYBOARD_KEYS["2"])
            self.assertTrue(app.has_pending_releases())
            self.assertTrue(app.retry_pending_releases())

        self.assertFalse(app.has_pending_releases())
        self.assertEqual(
            fake.calls,
            [
                [0, app.KEYEVENTF_KEYUP],
                [app.KEYEVENTF_KEYUP],
                [app.KEYEVENTF_KEYUP],
            ],
        )

    def test_recording_drops_unmatched_up_and_closes_down(self):
        recording = app.normalize_recording([
            {"type": "key_up", "key": "right", "at_ms": 0},
            {"type": "key_down", "key": "left", "at_ms": 10},
            {"type": "key_down", "key": "left", "at_ms": 11},
        ])
        self.assertEqual(recording, [
            {"type": "key_down", "key": "left", "at_ms": 10},
            {"type": "key_up", "key": "left", "at_ms": 20},
        ])

    def test_shared_hold_releases_after_last_owner(self):
        first = app.MacroConfig(True, "A", "f1", app.ACTION_HOLD, ["right", "none", "none", "none"], 100, "a")
        second = app.MacroConfig(True, "B", "f2", app.ACTION_HOLD, ["right", "none", "none", "none"], 100, "b")
        engine = app.MacroEngine(app.Config(macros=[first, second], toggle_profiles=[]))
        first, second = engine.config.macros
        calls = []
        engine.press_hold_item = lambda item: calls.append(("down", item))
        engine.release_hold_item = lambda item: calls.append(("up", item))

        engine._activate_macro(first)
        engine._activate_macro(second)
        engine._deactivate_macro(first)
        engine._deactivate_macro(second)

        self.assertEqual(calls, [("down", "right"), ("up", "right")])

    def test_hold_and_playback_release_after_last_owner(self):
        hold = app.MacroConfig(True, "按住", "f1", app.ACTION_HOLD, ["right", "none", "none", "none"], 100, "hold")
        playback = app.MacroConfig(
            True,
            "回放",
            "f2",
            app.ACTION_RECORDED,
            ["none"] * 4,
            100,
            "playback",
            app.PLAYBACK_ONCE,
            [
                {"type": "key_down", "key": "right", "at_ms": 0},
                {"type": "key_up", "key": "right", "at_ms": 100},
            ],
        )
        engine = app.MacroEngine(app.Config(macros=[hold, playback], toggle_profiles=[]))
        hold, playback = engine.config.macros
        calls = []

        with patch.object(app, "send_mouse_input", lambda flags: calls.append(flags)):
            engine._activate_macro(hold)
            engine._activate_macro(playback)
            engine._play_recorded_event(playback.id, playback.recording[0])
            engine._deactivate_macro(hold)
            self.assertEqual(calls, [app.MOUSEEVENTF_RIGHTDOWN])
            engine._play_recorded_event(playback.id, playback.recording[1])

        self.assertEqual(calls, [app.MOUSEEVENTF_RIGHTDOWN, app.MOUSEEVENTF_RIGHTUP])

    def test_playback_and_hold_release_after_last_owner(self):
        hold = app.MacroConfig(True, "按住", "f1", app.ACTION_HOLD, ["right", "none", "none", "none"], 100, "hold")
        playback = app.MacroConfig(
            True,
            "回放",
            "f2",
            app.ACTION_RECORDED,
            ["none"] * 4,
            100,
            "playback",
            app.PLAYBACK_ONCE,
            [
                {"type": "key_down", "key": "right", "at_ms": 0},
                {"type": "key_up", "key": "right", "at_ms": 100},
            ],
        )
        engine = app.MacroEngine(app.Config(macros=[hold, playback], toggle_profiles=[]))
        hold, playback = engine.config.macros
        calls = []

        with patch.object(app, "send_mouse_input", lambda flags: calls.append(flags)):
            engine._activate_macro(playback)
            engine._play_recorded_event(playback.id, playback.recording[0])
            engine._activate_macro(hold)
            engine._play_recorded_event(playback.id, playback.recording[1])
            self.assertEqual(calls, [app.MOUSEEVENTF_RIGHTDOWN])
            engine._deactivate_macro(hold)

        self.assertEqual(calls, [app.MOUSEEVENTF_RIGHTDOWN, app.MOUSEEVENTF_RIGHTUP])

    def test_cycle_press_restores_shared_hold(self):
        hold = app.MacroConfig(True, "按住", "f1", app.ACTION_HOLD, ["right", "none", "none", "none"], 100, "hold")
        engine = app.MacroEngine(app.Config(macros=[hold], toggle_profiles=[]))
        hold = engine.config.macros[0]
        fake = FakeUser32()

        with patch.object(app, "user32", fake):
            engine._activate_macro(hold)
            engine._press_cycle_item("right")
            engine._deactivate_macro(hold)

        self.assertEqual(
            fake.calls,
            [
                [app.MOUSEEVENTF_RIGHTDOWN],
                [app.MOUSEEVENTF_RIGHTDOWN, app.MOUSEEVENTF_RIGHTUP],
                [app.MOUSEEVENTF_RIGHTDOWN],
                [app.MOUSEEVENTF_RIGHTUP],
            ],
        )

    def test_failed_tracked_release_can_retry(self):
        engine = app.MacroEngine(app.Config(macros=[]))
        engine.right_is_down = True
        attempts = []

        def release_mouse(_flags):
            attempts.append(1)
            if len(attempts) == 1:
                raise OSError("temporary failure")

        with patch.object(app, "send_mouse_input", release_mouse):
            engine.release_all_inputs()
            self.assertTrue(engine.right_is_down)
            engine.release_all_inputs()

        self.assertFalse(engine.right_is_down)
        self.assertEqual(len(attempts), 2)

    def test_terminal_cleanup_retries_tracked_release(self):
        engine = app.MacroEngine(app.Config(macros=[]))
        engine.right_is_down = True
        attempts = []

        def release_mouse(_flags):
            attempts.append(1)
            if len(attempts) < 3:
                raise OSError("temporary failure")

        with patch.object(app, "send_mouse_input", release_mouse):
            released = engine.release_all_inputs_with_retry(attempts=3, delay_seconds=0)

        self.assertTrue(released)
        self.assertFalse(engine.right_is_down)
        self.assertEqual(len(attempts), 3)

    def test_engine_error_reports_cleanup_result(self):
        events = app.queue.Queue()
        engine = app.MacroEngine(app.Config(macros=[]), events)
        engine._run_loop = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        engine.release_all_inputs_with_retry = lambda: False

        engine._run()

        self.assertEqual(
            events.get_nowait(),
            {"type": "engine_error", "message": "boom", "released": False},
        )


if __name__ == "__main__":
    unittest.main()
