import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from doc_reader.modifier_gesture import ModifierGesture
from doc_reader.platform_tools import validate_selection_shortcut, default_dictation_key
from doc_reader.webapp import ReaderService


class ModifierTests(unittest.TestCase):
    def test_bare_right_windows_is_tap_without_start_menu_events(self):
        gesture = ModifierGesture(0x5C)
        self.assertEqual(gesture.event(0x5C, True), (True, [], "start"))
        self.assertEqual(gesture.event(0x5C, True), (True, [], ""))
        self.assertEqual(gesture.event(0x5C, False), (True, [], "tap"))
        self.assertEqual(gesture.event(0x5B, True), (False, [], ""))

    def test_normal_windows_chord_is_forwarded_with_matched_events(self):
        gesture = ModifierGesture(0x5C)
        gesture.event(0x5C, True)
        self.assertEqual(gesture.event(ord('E'), True), (False, [(0x5C, True)], "cancel"))
        self.assertEqual(gesture.event(ord('E'), False), (False, [], ""))
        self.assertEqual(gesture.event(0x5C, False), (True, [(0x5C, False)], "release"))
        self.assertEqual(gesture.event(0x5C, False), (False, [], ""))

    def test_modifier_joining_an_existing_chord_never_triggers(self):
        gesture = ModifierGesture(0x5C)
        self.assertEqual(gesture.event(0x5C, True, other_held=True), (True, [(0x5C, True)], ""))
        self.assertEqual(gesture.event(0x5C, False), (True, [(0x5C, False)], "release"))

    def test_only_left_alt_is_reserved_and_chords_cancel_dictation(self):
        gesture = ModifierGesture(0xA4)
        self.assertEqual(gesture.event(0xA5, True), (False, [], ""))
        self.assertEqual(gesture.event(0xA4, True), (True, [], "start"))
        self.assertEqual(gesture.event(9, True), (False, [(0xA4, True)], "cancel"))
        self.assertEqual(gesture.event(0xA4, False), (True, [(0xA4, False)], "release"))


class SetupTests(unittest.TestCase):
    def test_new_install_is_opt_in_and_recommended_keys_are_side_specific(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"DOC_READER_STT_ENABLED": "", "DOC_READER_DICTATION_KEY": ""}):
            reader = ReaderService(Path(folder))
            self.assertFalse(reader.native_status()["stt"]["enabled"])
            self.assertEqual(default_dictation_key(), "alt_l")
            self.assertEqual(validate_selection_shortcut("cmd_r"), ("cmd_r", ""))
            self.assertTrue(validate_selection_shortcut("<cmd>+r")[1])

    def test_partial_setup_survives_restart_without_changing_custom_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reader = ReaderService(root)
            reader._save_settings({"dictation_key":"f8", "selection_shortcut":"<ctrl>+<alt>+r"})
            with patch.object(reader, "state", return_value={}):
                reader.update_settings({"setup_step":2})
            restored = ReaderService(root)
            self.assertEqual(restored._settings_payload()["setup_step"], 2)
            self.assertFalse(restored._settings_payload()["setup_completed"])
            self.assertEqual(restored._hotkeys()["dictation_key"], "f8")
            for invalid in (-1, 4, True, "2"):
                with self.assertRaises(ValueError):
                    restored.update_settings({"setup_step":invalid})
            self.assertEqual(restored._settings_payload()["setup_step"], 2)
