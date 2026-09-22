import io
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from doc_reader.http_safety import MAX_UPLOAD_BYTES, read_body, validate_browser_write
from doc_reader.webapp import ReaderService


class RequestGuardsTests(unittest.TestCase):
    def test_browser_origin_must_match_app_host_and_port(self):
        for headers in ({}, {"Origin": "http://localhost:8766", "Host": "localhost:8766"}):
            validate_browser_write(headers)
        for headers in (
            {"Origin": "https://example.com", "Host": "localhost:8766"},
            {"Origin": "http://localhost:8767", "Host": "localhost:8766"},
            {"Sec-Fetch-Site": "cross-site"},
        ):
            with self.assertRaises(PermissionError):
                validate_browser_write(headers)

    def test_malformed_or_unbounded_upload_is_rejected(self):
        for length in ("-1", "bad", str(MAX_UPLOAD_BYTES + 1)):
            with self.assertRaises(ValueError):
                read_body(SimpleNamespace(headers={"Content-Length": length}, rfile=io.BytesIO(b"")))
        with self.assertRaises(ValueError):
            read_body(SimpleNamespace(headers={"Content-Length": "8"}, rfile=io.BytesIO(b"short")))

    def test_heartbeat_cannot_overwrite_hotkey_change(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"DOC_READER_ANALYSIS_ENABLED": "0"}):
            reader = ReaderService(Path(root))
            reader.state = lambda: {}
            reader.stt_status = lambda: {}
            loaded, release = threading.Event(), threading.Event()
            read = reader._settings

            def paused_read():
                settings = read()
                if threading.current_thread().name.startswith("heartbeat"):
                    loaded.set()
                    release.wait(2)
                return settings

            reader._settings = paused_read
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="heartbeat") as heartbeat_pool, \
                    ThreadPoolExecutor(max_workers=1) as user_pool:
                heartbeat = heartbeat_pool.submit(reader.update_native_dictation_status, {"recording": False})
                self.assertTrue(loaded.wait(1))
                update = user_pool.submit(reader.update_settings, {"dictation_key": "f8"})
                release.set()
                heartbeat.result(timeout=3)
                update.result(timeout=3)
            self.assertEqual(reader.native_status()["stt"]["hotkeys"]["dictation_key"], "f8")
