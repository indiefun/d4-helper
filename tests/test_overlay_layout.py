import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
