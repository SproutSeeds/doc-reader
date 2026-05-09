from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from doc_reader.webapp import ReaderService


class FakeSpeechHandler(BaseHTTPRequestHandler):
    calls: list[dict[str, object]] = []

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._json({
                "ok": True,
                "engines": {
                    "kokoro": {
                        "enabled": True,
                        "loaded": True,
                    },
                },
            })
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
        self.calls.append({"path": self.path, "payload": payload})
        if self.path != "/v1/audio/speech":
            self.send_error(404)
            return
        audio = f"fake-wav:{payload.get('text')}".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class WebappLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeSpeechHandler.calls = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeSpeechHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.speech_url = f"http://127.0.0.1:{self.server.server_port}"
        self.old_env = {
            "DOC_READER_WEB_SPEECH_BACKEND": os.environ.get("DOC_READER_WEB_SPEECH_BACKEND"),
            "DOC_READER_TTS_UMBRA_URL": os.environ.get("DOC_READER_TTS_UMBRA_URL"),
            "DOC_READER_ANALYSIS_ENABLED": os.environ.get("DOC_READER_ANALYSIS_ENABLED"),
            "DOC_READER_ANALYSIS_BACKEND": os.environ.get("DOC_READER_ANALYSIS_BACKEND"),
        }
        os.environ["DOC_READER_WEB_SPEECH_BACKEND"] = "tailscale-4090"
        os.environ["DOC_READER_TTS_UMBRA_URL"] = self.speech_url
        os.environ["DOC_READER_ANALYSIS_ENABLED"] = "0"
        os.environ["DOC_READER_ANALYSIS_BACKEND"] = "heuristic"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_library_upsert_prepares_audio_and_keeps_clawdad_filter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reader = ReaderService(Path(directory))
            item, queued = reader.upsert_library_item({
                "source": "clawdad",
                "source_item_id": "clawdad:test-message",
                "kind": "clawdad-message",
                "text": "Read this Clawdad message.",
                "prepare_audio": True,
                "source_meta": {
                    "projectPath": "/tmp/project",
                    "sessionId": "session-1",
                    "requestId": "request-1",
                },
            })
            self.assertTrue(queued)

            ready = self._wait_for_ready(reader, item.id)
            self.assertEqual(ready["audio"]["state"], "ready")
            data, content_type = reader.library_audio(item.id)
            self.assertEqual(content_type, "audio/wav")
            self.assertIn(b"Read this Clawdad message", data)

            state = reader.state()
            self.assertEqual(len(state["library"]), 1)
            self.assertEqual(len(state["clawdad"]), 1)
            self.assertEqual(len(state["readings"]), 0)
            self.assertEqual(FakeSpeechHandler.calls[0]["path"], "/v1/audio/speech")

            same_item, _queued_again = reader.upsert_library_item({
                "source": "clawdad",
                "source_item_id": "clawdad:test-message",
                "kind": "clawdad-message",
                "text": "Read this Clawdad message.",
                "prepare_audio": True,
            })
            self.assertEqual(same_item.id, item.id)

    def test_web_history_keeps_more_than_one_hundred_cards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reader = ReaderService(Path(directory))
            for index in range(125):
                reader.add_text(f"Reading item {index} has several countable words.")

            state = reader.state()
            self.assertEqual(len(state["library"]), 125)
            self.assertEqual(state["metrics"]["tts_items"], 125)
            self.assertGreater(state["metrics"]["tts_words"], 125)

    def test_metrics_split_stt_and_tts_words(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reader = ReaderService(Path(directory))
            reader.add_text("read aloud words only", label="Text", kind="text")
            reader.add_text("dictated words arrive here", label="Dictation", kind="dictation")

            metrics = reader.metrics_snapshot()
            self.assertEqual(metrics["tts_words"], 4)
            self.assertEqual(metrics["stt_words"], 4)
            self.assertEqual(metrics["tts_items"], 1)
            self.assertEqual(metrics["stt_items"], 1)

    def test_heuristic_analysis_writes_style_map(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reader = ReaderService(Path(directory))
            reader.add_text(
                "We should add structure to the recordings. What did we discuss?",
                label="Dictation",
                kind="dictation",
            )

            analysis = reader.run_library_analysis_once(reason="test")
            self.assertEqual(analysis["pending_items"], 0)
            self.assertEqual(analysis["items_analyzed"], 1)
            self.assertEqual(analysis["style_map"]["items_analyzed"], 1)
            self.assertTrue((Path(directory) / "library-analysis.json").is_file())

    def _wait_for_ready(self, reader: ReaderService, item_id: str) -> dict[str, object]:
        deadline = time.time() + 5
        last = {}
        while time.time() < deadline:
            last = reader.library_item_payload(item_id=item_id)
            if last.get("audio", {}).get("state") == "ready":
                return last
            time.sleep(0.05)
        self.fail(f"library audio did not become ready: {last}")


if __name__ == "__main__":
    unittest.main()
