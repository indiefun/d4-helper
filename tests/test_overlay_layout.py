import json
import queue
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import right_hold_toggle as app


class OverlayWindowTests(unittest.TestCase):
    def test_target_rect_survives_focus_moving_to_own_overlay(self):
        config = app.Config(macros=[], toggle_profiles=[])
        engine = app.MacroEngine(config)
        foregrounds = iter([
            (100, "暗黑破坏神IV", "Diablo IV.exe"),
            (200, "D4Helper", "D4Helper.exe"),
        ])
        sleeps = 0

        def stop_after_two_iterations(_seconds):
            nonlocal sleeps
            sleeps += 1
            if sleeps >= 2:
                engine.running = False

        engine._read_foreground_window = lambda: next(foregrounds)
        engine.running = True
        with (
            patch.object(app, "get_window_rect", return_value=app.wintypes.RECT(80, 60, 1680, 960)),
            patch.object(app, "is_key_down", return_value=False),
            patch.object(app.time, "sleep", side_effect=stop_after_two_iterations),
        ):
            engine._run_loop()

        snapshot = engine.snapshot()
        self.assertFalse(snapshot.target_active)
        self.assertEqual(snapshot.target_window_rect, (80, 60, 1680, 960))

    def test_window_rect_copy_is_independent(self):
        original = app.wintypes.RECT(10, 20, 1010, 820)
        copied = app.copy_window_rect(original)

        original.left = 999

        self.assertIsNotNone(copied)
        self.assertEqual(app.rect_to_tuple(copied), (10, 20, 1010, 820))

    @patch.object(app, "virtual_desktop_bounds", return_value=(0, 0, 1920, 1080))
    def test_overlay_avoidance_moves_away_from_cursor(self, _bounds):
        position = app.choose_overlay_avoid_position(
            current_x=20,
            current_y=20,
            width=252,
            height=56,
            target_rect=(0, 0, 1920, 1080),
            cursor=(30, 30),
            distance=72,
        )

        self.assertIsNotNone(position)
        self.assertGreaterEqual(
            app.point_to_rect_distance_squared((30, 30), position[0], position[1], 252, 56),
            72 ** 2,
        )

    def test_overlay_avoidance_handles_missing_cursor_or_target(self):
        self.assertIsNone(
            app.choose_overlay_avoid_position(20, 20, 252, 56, None, (30, 30), 72)
        )
        self.assertIsNone(
            app.choose_overlay_avoid_position(20, 20, 252, 56, (0, 0, 1920, 1080), None, 72)
        )


class OverlayAvoidanceTests(unittest.TestCase):
    def setUp(self):
        self.bounds = self.enterContext(patch.object(app, "virtual_desktop_bounds", return_value=(0, 0, 1920, 1080)))
        self.cursor = self.enterContext(patch.object(app, "get_cursor_position", return_value=(30, 30)))
        self.clock = self.enterContext(patch.object(app.time, "monotonic", return_value=10.0))
        self.enterContext(patch.object(app.tk, "Toplevel"))
        self.enterContext(patch.object(app.tk, "Canvas"))
        self.config = app.Config(macros=app.default_macros(), toggle_profiles=[])
        self.snapshot = app.Snapshot(True, {}, self.config, "game", "game.exe", (0, 0, 1920, 1080))
        self.engine = Mock()
        self.engine.snapshot.return_value = self.snapshot
        self.overlay = app.OverlayWindow(Mock(), self.engine)
        self.overlay.window.state.return_value = "normal"

    def test_avoidance_stays_visible_for_partial_and_negative_screen_coordinates(self):
        for desktop, target, cursor in (
            ((0, 0, 1920, 1080), (0, 0, 3000, 1080), (30, 30)),
            ((-1920, -1080, 1920, 1080), (-1920, -1080, 0, 0), (-30, -30)),
        ):
            with self.subTest(desktop=desktop):
                self.bounds.return_value = desktop
                position = app.choose_overlay_avoid_position(20, 20, 252, 146, target, cursor, 72)
                self.assertIsNotNone(position)
                x, y = position
                self.assertGreaterEqual(x, max(desktop[0], target[0]))
                self.assertGreaterEqual(y, max(desktop[1], target[1]))
                self.assertLessEqual(x + 252, min(desktop[2], target[2]))
                self.assertLessEqual(y + 146, min(desktop[3], target[3]))

    def test_avoidance_does_not_move_when_no_safe_destination_fits(self):
        for bounds in ((0, 0, 200, 100), (0, 0, 300, 180), (3000, 0, 4000, 1080)):
            with self.subTest(bounds=bounds):
                self.assertIsNone(app.choose_overlay_avoid_position(20, 20, 252, 146, bounds, (150, 90), 72))

    def test_avoidance_stays_put_without_saving_and_respects_cooldown(self):
        self.overlay.refresh()
        first_position = self.overlay._avoid_position
        self.assertIsNotNone(first_position)
        first_geometry = self.overlay.window.geometry.call_args
        self.clock.return_value = 10.1
        self.cursor.return_value = first_position
        self.overlay.refresh()
        self.assertEqual(self.overlay._avoid_position, first_position)

        self.clock.return_value = 11.0
        self.cursor.return_value = (30, 30)
        self.overlay.refresh()
        self.assertEqual(self.overlay.window.geometry.call_args, first_geometry)
        self.clock.return_value = 12.0
        self.cursor.return_value = first_position
        self.overlay.refresh()
        self.assertNotEqual(self.overlay._avoid_position, first_position)

    def test_overlay_uses_fixed_top_left_anchor_when_avoidance_is_disabled(self):
        self.config.overlay_avoid_mouse = False
        self.engine.snapshot.return_value = replace(
            self.snapshot, target_window_rect=(80, 60, 1680, 960)
        )
        self.overlay.refresh()

        self.overlay.window.geometry.assert_called_with(
            app.window_geometry(252, self.overlay.height, 100, 80)
        )
        self.cursor.assert_not_called()

    def test_proximity_uses_fixed_position_when_cursor_is_near(self):
        self.cursor.return_value = (5, 30)
        self.overlay.refresh()
        self.assertIsNotNone(self.overlay._avoid_position)

    def test_height_growth_keeps_avoided_window_on_screen(self):
        self.engine.snapshot.return_value = replace(self.snapshot, recording_status="recording")
        self.overlay.refresh()
        self.assertIsNotNone(self.overlay._avoid_position)
        self.engine.snapshot.return_value = self.snapshot
        self.overlay.refresh()
        self.assertIsNotNone(self.overlay._avoid_position)
        self.assertLessEqual(self.overlay._avoid_position[1] + self.overlay.height, 1080)

    def test_old_config_gets_defaults_and_avoidance_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps({
                    "macros": [],
                    "toggle_profiles": [],
                    "overlay_x": 900,
                    "overlay_y": -300,
                    "route_enabled": True,
                    "route_trigger": "f11",
                    "overlay_layout_trigger": "f10",
                    "route_x": 1000,
                    "route_y": 120,
                    "route_size": "large",
                    "route_opacity": 0.9,
                    "route_last_selected": "01",
                }),
                encoding="utf-8",
            )
            config = app.load_config(path)
            self.assertTrue(config.overlay_avoid_mouse)
            self.assertEqual(config.overlay_avoid_distance, 72)
            config.overlay_avoid_mouse = False
            config.overlay_avoid_distance = 120
            app.save_config(path, app.clone_config(config))
            loaded = app.load_config(path)
            self.assertFalse(loaded.overlay_avoid_mouse)
            self.assertEqual(loaded.overlay_avoid_distance, 120)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["overlay_avoid_distance"], 120)
            for removed_key in (
                "overlay_x", "overlay_y", "route_enabled", "route_trigger",
                "overlay_layout_trigger",
                "route_x", "route_y", "route_size", "route_opacity",
                "route_last_selected",
            ):
                self.assertNotIn(removed_key, saved)

    def test_f10_and_f11_are_available_as_macro_triggers(self):
        config = app.Config(
            window_title_contains="Diablo IV",
            process_name="Diablo IV.exe",
            macros=[
                app.MacroConfig(True, "F10 宏", "f10", app.ACTION_HOLD, ["right"], id="f10"),
                app.MacroConfig(True, "F11 宏", "f11", app.ACTION_HOLD, ["left"], id="f11"),
            ],
            toggle_profiles=[],
        )

        app.validate_config(config)
        self.assertEqual([macro.trigger for macro in config.macros], ["f10", "f11"])

        engine = app.MacroEngine(config, queue.Queue())
        trigger_checks = {}

        def key_down(virtual_key):
            trigger_checks[virtual_key] = trigger_checks.get(virtual_key, 0) + 1
            if virtual_key in (app.VK_F10, app.VK_F11):
                return trigger_checks[virtual_key] > 1
            return False

        engine._read_foreground_window = lambda: (100, "Diablo IV", "Diablo IV.exe")
        engine.running = True

        def stop_after_iteration(_seconds):
            engine.running = False

        with (
            patch.object(app, "is_key_down", side_effect=key_down),
            patch.object(app, "get_window_rect", return_value=app.wintypes.RECT(0, 0, 1920, 1080)),
            patch.object(engine, "_toggle_macro") as toggle_macro,
            patch.object(engine, "release_all_inputs"),
            patch.object(app.time, "sleep", side_effect=stop_after_iteration),
        ):
            engine._run_loop()

        self.assertEqual(
            [call.args[0].id for call in toggle_macro.call_args_list],
            ["f10", "f11"],
        )
        self.assertTrue(engine.event_queue.empty())

    def test_invalid_avoidance_distance_is_rejected(self):
        for distance in (0, 401):
            with self.subTest(distance=distance):
                self.config.overlay_avoid_distance = distance
                with self.assertRaises(ValueError):
                    app.validate_config(self.config)


if __name__ == "__main__":
    unittest.main()
