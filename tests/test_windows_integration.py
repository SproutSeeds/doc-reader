from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from doc_reader import platform_tools, windows_app, windows_helper


class ProcessOwnershipTests(unittest.TestCase):
    def test_only_exact_service_and_data_folder_match(self):
        marker = r"doc_reader_root=C:\Users\Test User\reader"
        args = ["python.exe", "-X", marker, "-m", "doc_reader.webapp", "--port", "8766"]
        self.assertTrue(windows_app._matches_service(args, "doc_reader.webapp", marker))
        for changed in (
            ["python.exe", "-X", marker + "-preview", "-m", "doc_reader.webapp"],
            ["python.exe", "-X", marker, "-m", "doc_reader.webapp_extra"],
            ["python.exe", "-c", " ".join(args[1:])],
            ["python.exe", "-m", "doc_reader.webapp"],
        ):
            self.assertFalse(windows_app._matches_service(changed, "doc_reader.webapp", marker))

    def test_stale_pid_file_never_terminates_unrelated_process(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"DOC_READER_MANAGED_ROOT": root}), \
                patch.object(windows_app, "IS_WINDOWS", True), \
                patch.object(windows_app, "_find_stray_pids", return_value=[]), \
                patch.object(windows_app, "kill_process_tree") as kill:
            windows_app._write_pid("web", 12345)
            windows_app.stop_service("web", quiet=True)
            kill.assert_not_called()
            self.assertFalse(windows_app._pid_file("web").exists())

    def test_owned_service_can_be_recovered_without_pid_file(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"DOC_READER_MANAGED_ROOT": root}), \
                patch.object(windows_app, "IS_WINDOWS", True), \
                patch.object(windows_app, "_find_stray_pids", return_value=[45678]), \
                patch.object(windows_app, "kill_process_tree") as kill:
            windows_app.stop_service("web", quiet=True)
            kill.assert_called_once_with(45678, force=True)

    @unittest.skipUnless(sys.platform == "win32", "Windows command-line API")
    def test_windows_command_line_round_trip(self):
        args = [sys.executable, "-X", r"doc_reader_root=C:\Users\Test User\reader", "-m", "doc_reader.webapp"]
        self.assertEqual(windows_app._command_arguments(subprocess.list2cmdline(args)), args)

    @unittest.skipUnless(sys.platform == "win32", "Windows process inventory")
    def test_actual_unrelated_python_survives_stale_pid_file(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"DOC_READER_MANAGED_ROOT": root}):
                windows_app._write_pid("web", process.pid)
                windows_app.stop_service("web", quiet=True)
                self.assertIsNone(process.poll())
        finally:
            process.terminate()
            process.wait(timeout=5)

    def test_open_repairs_the_whole_stack(self):
        with patch.object(windows_app, "cmd_start", return_value=0) as start, \
                patch.object(windows_app.webbrowser, "open") as open_browser:
            self.assertEqual(windows_app.cmd_open(), 0)
            start.assert_called_once_with(open_browser=False, quiet=True)
            open_browser.assert_called_once()


class PlatformHotkeyTests(unittest.TestCase):
    def test_mac_default_can_be_restored_and_unsupported_keys_are_refused(self):
        with patch.object(platform_tools, "IS_MACOS", True):
            default = platform_tools.DEFAULT_MAC_SELECTION_HOTKEY
            self.assertEqual(platform_tools.validate_selection_shortcut(default), (default, ""))
            self.assertIn(default, [entry["value"] for entry in platform_tools.hotkey_options()["selection"]])
            for key in ("caps_lock", "scroll_lock", "f21", "f24"):
                self.assertEqual(platform_tools.validate_dictation_key(key)[0], "")

    def test_windows_special_keys_remain_available(self):
        with patch.object(platform_tools, "IS_MACOS", False):
            for key in ("caps_lock", "scroll_lock", "f21", "f24"):
                self.assertEqual(platform_tools.validate_dictation_key(key), (key, ""))
            self.assertEqual(platform_tools.validate_selection_shortcut("<cmd>+r")[0], "")

    def test_dll_search_handle_stays_alive(self):
        with tempfile.TemporaryDirectory() as root:
            lib = Path(root) / "lib"
            lib.mkdir()
            handle = object()
            with patch.dict(sys.modules, {"torch": SimpleNamespace(__file__=str(Path(root) / "__init__.py"))}), \
                    patch.object(platform_tools, "IS_WINDOWS", True), \
                    patch.object(platform_tools.os, "add_dll_directory", return_value=handle, create=True), \
                    patch.dict(os.environ), patch.object(platform_tools, "_DLL_DIRECTORY_HANDLES", []):
                platform_tools.configure_windows_dll_search()
                self.assertIn(handle, platform_tools._DLL_DIRECTORY_HANDLES)


class ClipboardPreservationTests(unittest.TestCase):
    def test_snapshot_keeps_rich_text_and_binary_formats(self):
        from PySide6.QtCore import QMimeData

        data = QMimeData()
        data.setText("Text")
        data.setHtml("<b>Text</b>")
        data.setData("application/octet-stream", b"\x00\xff\x01")
        clipboard = SimpleNamespace(mimeData=lambda: data)
        snapshot = windows_helper._copy_clipboard_data(clipboard)
        data.clear()
        self.assertEqual(snapshot.text(), "Text")
        self.assertEqual(snapshot.html(), "<b>Text</b>")
        self.assertEqual(bytes(snapshot.data("application/octet-stream")), b"\x00\xff\x01")


if __name__ == "__main__":
    unittest.main()
