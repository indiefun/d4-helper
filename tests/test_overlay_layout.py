import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import right_hold_toggle as app


class OverlayLayoutTests(unittest.TestCase):
    def test_updating_one_overlay_preserves_the_other_position(self):
        config = app.Config(
            macros=[],
            toggle_profiles=[],
            overlay_x=20,
            overlay_y=30,
            route_x=1000,
            route_y=120,
        )
        engine = app.MacroEngine(config)

        updated = engine.update_overlay_position("status", 250, -40)
        self.assertEqual((updated.overlay_x, updated.overlay_y), (250, -40))
        self.assertEqual((updated.route_x, updated.route_y), (1000, 120))

        updated = engine.update_overlay_position("route", -300, 460)
        self.assertEqual((updated.overlay_x, updated.overlay_y), (250, -40))
        self.assertEqual((updated.route_x, updated.route_y), (-300, 460))

    def test_target_rect_survives_focus_moving_to_own_overlay(self):
        config = app.Config(macros=[], toggle_profiles=[], route_enabled=False)
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

    def test_drag_anchor_is_an_independent_rect_copy(self):
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
        self.persist_position = Mock()
        self.overlay = app.OverlayWindow(Mock(), self.engine, self.persist_position)
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
        self.assertEqual((self.config.overlay_x, self.config.overlay_y), (20, 20))
        self.persist_position.assert_not_called()

    def test_layout_mode_and_disabled_setting_restore_saved_position(self):
        for layout_mode in (True, False):
            with self.subTest(layout_mode=layout_mode):
                self.overlay.layout_mode = False
                self.config.overlay_avoid_mouse = True
                self.overlay.refresh()
                self.assertIsNotNone(self.overlay._avoid_position)
                self.cursor.reset_mock()
                if layout_mode:
                    with patch.object(self.overlay, "_apply_window_style"):
                        self.overlay.set_layout_mode(True)
                else:
                    self.config.overlay_avoid_mouse = False
                    self.overlay.refresh()
                self.assertIsNone(self.overlay._avoid_position)
                self.overlay.window.geometry.assert_called_with(app.window_geometry(252, self.overlay.height, 20, 20))
                self.cursor.assert_not_called()
                self.persist_position.assert_not_called()

    def test_proximity_uses_visible_position_when_saved_position_is_offscreen(self):
        self.config.overlay_x = -5000
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
            path.write_text('{"macros": [], "toggle_profiles": []}', encoding="utf-8")
            config = app.load_config(path)
            self.assertTrue(config.overlay_avoid_mouse)
            self.assertEqual(config.overlay_avoid_distance, 72)
            config.overlay_avoid_mouse = False
            config.overlay_avoid_distance = 120
            app.save_config(path, app.clone_config(config))
            loaded = app.load_config(path)
            self.assertFalse(loaded.overlay_avoid_mouse)
            self.assertEqual(loaded.overlay_avoid_distance, 120)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["overlay_avoid_distance"], 120)

    def test_invalid_avoidance_distance_is_rejected(self):
        for distance in (0, 401):
            with self.subTest(distance=distance):
                self.config.overlay_avoid_distance = distance
                with self.assertRaises(ValueError):
                    app.validate_config(self.config)


if __name__ == "__main__":
    unittest.main()
