import json
import queue
import tempfile
import tkinter as tk
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock, patch

import right_hold_toggle as app


def role_profile(profile_id, name, key):
    macro = app.MacroConfig(
        True, "技能", "f1", app.ACTION_PRESS_CYCLE, [key], 150, "skill",
    )
    return app.ProfileConfig(
        profile_id, name, [macro],
        [app.ToggleProfile(True, "middle", [macro.id], "launch")],
    )


def role_config():
    return app.normalize_config(app.Config(
        profiles=[role_profile("barbarian", "野蛮人", "1"), role_profile("sorcerer", "法师", "2")],
        active_profile_id="barbarian",
    ))


class ProfileStorageTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "config.json"

    def test_version_file_with_windows_utf8_bom_is_read_without_extra_prefix(self):
        version_path = self.path.parent / "VERSION"
        version_path.write_text("1.7.0\n", encoding="utf-8-sig")
        with patch.object(app, "VERSION_PATH", version_path):
            self.assertEqual(app.read_app_version(), "1.7.0")

    def test_legacy_config_migrates_without_losing_macros_or_launch_selections(self):
        macros = app.default_macros()
        macros[0].name = "我的角色技能"
        macros[0].recording = [{"type": "key_down", "key": "1", "at_ms": 0}]
        legacy = app.Config(macros=macros, toggle_profiles=app.default_toggle_profiles(macros))
        data = asdict(legacy)
        del data["profiles"], data["active_profile_id"]
        self.path.write_text(json.dumps(data), encoding="utf-8")

        loaded = app.load_config(self.path)
        reloaded = app.load_config(self.path)

        self.assertEqual(len(loaded.profiles), 1)
        self.assertEqual(loaded.profiles[0].name, "默认配置")
        self.assertEqual(loaded.active_profile_id, reloaded.active_profile_id)
        self.assertEqual(asdict(loaded), asdict(reloaded))
        self.assertEqual(loaded.macros[0].name, "我的角色技能")
        self.assertEqual(loaded.macros[0].recording[-1]["type"], "key_up")
        self.assertEqual(loaded.toggle_profiles[0].macro_ids, legacy.toggle_profiles[0].macro_ids)

    def test_round_trip_restores_selected_role_and_independent_launch_groups(self):
        config = role_config()
        config.macros[0].interval_ms = 275
        config.toggle_profiles[0].enabled = False
        config = app.select_config_profile(config, "sorcerer")
        config.macros[0].interval_ms = 500
        app.save_config(self.path, config)

        loaded = app.load_config(self.path)

        self.assertEqual(loaded.active_profile_id, "sorcerer")
        self.assertEqual(loaded.macros[0].sequence[0], "2")
        self.assertEqual(loaded.macros[0].interval_ms, 500)
        self.assertTrue(loaded.toggle_profiles[0].enabled)
        first = app.select_config_profile(loaded, "barbarian")
        self.assertEqual(first.macros[0].interval_ms, 275)
        self.assertFalse(first.toggle_profiles[0].enabled)
        self.assertEqual(first.toggle_profiles[0].macro_ids, ["skill"])
        self.assertEqual(len(json.loads(self.path.read_text(encoding="utf-8"))["profiles"]), 2)

    def test_new_empty_profile_stays_empty_after_restart(self):
        config = role_config()
        config.profiles.append(app.ProfileConfig("empty", "新角色", [], []))
        app.save_config(self.path, app.select_config_profile(config, "empty"))

        loaded = app.load_config(self.path)

        self.assertEqual(loaded.macros, [])
        self.assertEqual(loaded.toggle_profiles, [])
        self.assertEqual(len(loaded.profiles[0].macros), 1)

    def test_deleted_active_id_falls_back_to_first_profile(self):
        data = asdict(role_config())
        del data["macros"], data["toggle_profiles"]
        data["active_profile_id"] = "missing"
        self.path.write_text(json.dumps(data), encoding="utf-8")

        loaded = app.load_config(self.path)

        self.assertEqual(loaded.active_profile_id, "barbarian")
        self.assertEqual(loaded.macros[0].sequence[0], "1")

    def test_clone_and_switch_do_not_modify_other_role_or_source(self):
        original = role_config()
        config = app.select_config_profile(original, "sorcerer")
        config.macros[0].sequence[0] = "3"
        config.toggle_profiles[0].macro_ids.clear()
        config = app.select_config_profile(config, "barbarian")

        self.assertEqual(config.macros[0].sequence[0], "1")
        self.assertEqual(config.toggle_profiles[0].macro_ids, ["skill"])
        self.assertEqual(original.profiles[1].macros[0].sequence[0], "2")
        self.assertEqual(original.profiles[1].toggle_profiles[0].macro_ids, ["skill"])

    def test_same_hotkeys_work_across_roles_but_conflicts_within_role_are_rejected(self):
        config = role_config()
        app.validate_config(config)
        config.profiles[1].toggle_profiles[0].trigger = "f1"
        with self.assertRaisesRegex(ValueError, "法师.*同一个按键"):
            app.validate_config(config)

    def test_profile_names_cannot_be_empty_or_duplicate(self):
        for name in ("", "  ", "野蛮人"):
            with self.subTest(name=name):
                config = role_config()
                config.profiles[1].name = name
                with self.assertRaises(ValueError):
                    app.validate_config(config)

    def test_failed_atomic_save_preserves_original_file(self):
        app.save_config(self.path, role_config())
        before = self.path.read_bytes()
        with patch.object(Path, "replace", side_effect=PermissionError("文件被占用")):
            with self.assertRaises(PermissionError):
                app.save_config(self.path, app.select_config_profile(role_config(), "sorcerer"))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])


class ProfileWindowTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "config.json"
        self.enterContext(patch.object(app, "FastInputKernel", return_value=Mock(available=False)))
        self.errors = self.enterContext(patch.object(app.messagebox, "showerror"))
        self.engine = app.MacroEngine(role_config(), queue.Queue())
        app.save_config(self.path, self.engine.config)
        self.window = app.ConfigWindow(self.root, self.engine, queue.Queue(), self.path)
        self.enterContext(patch.object(self.window, "_reveal_window"))

    def test_clicking_tabs_saves_edits_and_restores_independent_settings(self):
        self.window.macro_vars[0]["name"].set("旋风斩")
        self.window.macro_vars[0]["interval"].set("250")
        self.window.toggle_profile_vars[0]["enabled"].set(False)
        self.window.profile_tabs.winfo_children()[1].invoke()

        self.assertEqual(self.engine.config.active_profile_id, "sorcerer")
        self.assertEqual(self.window.macro_vars[0]["name"].get(), "技能")
        self.assertTrue(self.window.toggle_profile_vars[0]["enabled"].get())
        self.window.macro_vars[0]["slot1"].set("3")
        self.window.profile_tabs.winfo_children()[0].invoke()

        self.assertEqual(self.window.macro_vars[0]["name"].get(), "旋风斩")
        self.assertEqual(self.window.macro_vars[0]["interval"].get(), "250")
        self.assertFalse(self.window.toggle_profile_vars[0]["enabled"].get())
        loaded = app.load_config(self.path)
        self.assertEqual(loaded.active_profile_id, "barbarian")
        self.assertEqual(loaded.profiles[1].macros[0].sequence[0], "3")
        self.errors.assert_not_called()

    def test_create_and_rename_profile_keeps_existing_role_and_new_role_empty(self):
        self.window.macro_vars[0]["name"].set("已编辑技能")
        self.window.overlay_enabled_var.set(False)
        with patch.object(app.simpledialog, "askstring") as ask_name:
            self.window.add_profile()
        ask_name.assert_not_called()
        created_id = self.window.active_profile_id
        self.assertEqual(len(self.window.profiles), 3)
        self.assertEqual(self.window.profiles[2].name, "配置 1")
        self.assertEqual(self.window.macro_vars, [])
        self.assertEqual(self.window.toggle_profile_vars, [])
        self.assertFalse(self.window.overlay_enabled_var.get())
        self.window.add_macro_row()
        self.window.macro_vars[0]["name"].set("风暴")
        self.window.add_toggle_profile_row()
        with patch.object(app.simpledialog, "askstring", return_value="风暴德鲁伊"):
            self.window.rename_profile()

        loaded = app.load_config(self.path)
        self.assertEqual(loaded.active_profile_id, created_id)
        self.assertEqual(loaded.profiles[2].name, "风暴德鲁伊")
        self.assertEqual(loaded.macros[0].name, "风暴")
        self.assertEqual(len(loaded.toggle_profiles), 1)
        self.assertEqual(loaded.profiles[0].macros[0].name, "已编辑技能")
        self.assertFalse(loaded.overlay_enabled)
        self.errors.assert_not_called()

    def test_repeated_create_assigns_unique_names_and_switches_without_prompt(self):
        with patch.object(app.simpledialog, "askstring") as ask_name:
            self.window.add_profile()
            self.window.add_profile()
            self.window.add_profile()
        ask_name.assert_not_called()
        loaded = app.load_config(self.path)
        self.assertEqual([profile.name for profile in loaded.profiles[2:]], ["配置 1", "配置 2", "配置 3"])
        self.assertEqual(loaded.active_profile_id, loaded.profiles[-1].id)
        self.assertEqual(len({profile.id for profile in loaded.profiles}), 5)
        self.errors.assert_not_called()

    def test_duplicate_name_and_cancel_leave_profiles_unchanged(self):
        before = self.path.read_bytes()
        with patch.object(app.simpledialog, "askstring", return_value=None):
            self.window.rename_profile()
        self.errors.assert_not_called()
        with patch.object(app.simpledialog, "askstring", return_value="法师"):
            self.window.rename_profile()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.window.active_profile_id, "barbarian")
        self.errors.assert_called_once()

    def test_invalid_draft_or_failed_save_keeps_current_tab_and_edits(self):
        before = self.path.read_bytes()
        self.window.macro_vars[0]["interval"].set("无效")
        self.window.profile_tabs.winfo_children()[1].invoke()
        self.assertEqual(self.window.active_profile_id, "barbarian")
        self.assertEqual(self.window.profile_tab_var.get(), "barbarian")
        self.assertEqual(self.window.macro_vars[0]["interval"].get(), "无效")
        self.assertEqual(self.path.read_bytes(), before)
        self.window.macro_vars[0]["interval"].set("300")
        with patch.object(app, "save_config", side_effect=PermissionError("文件被占用")):
            self.window.profile_tabs.winfo_children()[1].invoke()
        self.assertEqual(self.engine.config.active_profile_id, "barbarian")
        self.assertEqual(self.window.profile_tab_var.get(), "barbarian")
        self.assertEqual(self.window.macro_vars[0]["interval"].get(), "300")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.errors.call_count, 2)

    def test_deselected_launch_macro_stays_deselected_after_rerender_and_switch(self):
        self.window.toggle_profile_vars[0]["selected_vars"]["skill"].set(False)
        self.window.add_macro_row()
        self.assertFalse(self.window.toggle_profile_vars[0]["selected_vars"]["skill"].get())
        self.window.switch_profile("sorcerer")
        self.window.switch_profile("barbarian")
        self.assertFalse(self.window.toggle_profile_vars[0]["selected_vars"]["skill"].get())
        self.assertEqual(self.engine.config.toggle_profiles[0].macro_ids, [])

    def test_switch_stops_macros_and_releases_inputs_before_new_role_can_run(self):
        self.engine.active_macros.add("skill")
        self.engine.next_press_at["skill"] = 123
        self.engine.sequence_index["skill"] = 3
        self.engine.target_active = True
        self.engine.right_is_down = True
        self.engine.recording_status = "recording"
        with (
            patch.object(app, "send_mouse_input") as send_mouse,
            patch.object(app, "is_key_down", return_value=True),
        ):
            self.window.switch_profile("sorcerer")
        send_mouse.assert_called_once_with(app.MOUSEEVENTF_RIGHTUP)
        self.assertFalse(self.engine.right_is_down)
        self.assertEqual(self.engine.active_macros, set())
        self.assertEqual(self.engine.next_press_at, {})
        self.assertEqual(self.engine.sequence_index, {})
        self.assertEqual(self.engine.recording_status, "idle")
        self.assertTrue(self.engine.last_trigger_down["profile:launch"])
        self.assertEqual(self.engine.config.macros[0].sequence[0], "2")
        self.assertIsNone(self.engine.snapshot().config.profiles)
        self.assertEqual(len(self.engine.snapshot(include_profiles=True).config.profiles), 2)
        self.errors.assert_not_called()

    def test_delete_role_and_restore_defaults_do_not_erase_other_role(self):
        with patch.object(app.messagebox, "askyesno", return_value=False):
            self.window.remove_profile()
        self.assertEqual(len(self.window.profiles), 2)
        self.window.defaults()
        self.assertEqual(len(self.engine.config.macros), len(app.default_macros()))
        self.window.switch_profile("sorcerer")
        self.assertEqual(len(self.window.macro_vars), 1)
        self.window.macro_vars[0]["interval"].set("无效")
        with patch.object(app.messagebox, "askyesno", return_value=True):
            self.window.remove_profile()
            self.window.remove_profile()
        loaded = app.load_config(self.path)
        self.assertEqual(len(loaded.profiles), 1)
        self.assertEqual(loaded.active_profile_id, "barbarian")
        self.assertIn("disabled", self.window.delete_profile_button.state())
        self.errors.assert_not_called()

    def test_recording_completed_before_switch_stays_in_original_role(self):
        events = [{"type": "key_down", "key": "1", "at_ms": 0}]
        self.engine.recording_status = "recording"
        self.engine.recorded_events = events
        with patch.object(self.engine, "release_all_inputs"):
            self.engine._finish_recording_locked()
        event = self.engine.event_queue.get_nowait()
        self.window.switch_profile("sorcerer")
        self.window.macro_vars[0]["name"].set("法师未保存草稿")
        self.window.add_recorded_macro(event["events"], event["profile_id"])
        self.assertEqual(self.window.macro_vars[0]["name"].get(), "法师未保存草稿")
        self.assertEqual(len(self.window.macro_vars), 1)
        self.window.switch_profile("barbarian")
        self.assertEqual(len(self.window.macro_vars), 2)
        self.assertEqual(self.window.macro_vars[1]["recording"][0]["key"], "1")
        self.assertFalse(self.window.macro_vars[1]["enabled"].get())
        self.errors.assert_not_called()

    def test_long_macro_list_is_scrollable_and_window_fits_screen(self):
        self.window.set_macro_rows([app.blank_macro_config(index) for index in range(1, 26)])
        self.window._fit_to_content()
        self.root.update_idletasks()
        width, height = (int(value) for value in self.root.geometry().split("+")[0].split("x"))
        self.assertLessEqual(height, self.root.winfo_screenheight() - 100)
        self.assertLessEqual(width, self.root.winfo_screenwidth() - 60)
        self.window.content_canvas.yview_moveto(1)
        self.assertGreater(self.window.content_canvas.yview()[0], 0)


if __name__ == "__main__":
    unittest.main()
