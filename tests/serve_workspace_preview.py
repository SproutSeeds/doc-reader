"""Isolated browser QA server. Playback is simulated; no microphone or helper starts.

Run from the repository: python tests/serve_workspace_preview.py
The temporary library is discarded when the server exits.
"""
from __future__ import annotations

import argparse
import io
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import wave
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_webapp_library import FakeSpeechHandler
from doc_reader.webapp import DocReaderHandler, DocReaderHTTPServer, ReaderService


class PreviewSpeech(FakeSpeechHandler):
    def do_POST(self):
        if self.path != "/v1/audio/speech":
            return super().do_POST()
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        audio = io.BytesIO()
        with wave.open(audio, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\0\0" * 16000)
        body = audio.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class PreviewReader(ReaderService):
    preview_active = None
    preview_paused = False

    def state(self):
        data = super().state()
        data.update(running=bool(self.preview_active and not self.preview_paused),
                    paused=bool(self.preview_active and self.preview_paused),
                    active_id=self.preview_active)
        for group in ("items", "library", "readings", "dictations", "clawdad"):
            for item in data[group]:
                item["playing"] = item["id"] == self.preview_active and not self.preview_paused
                item["paused"] = item["id"] == self.preview_active and self.preview_paused
        return data

    def play(self, item_id):
        if self._find_item(item_id) is None:
            raise KeyError("History item not found.")
        self.preview_active = item_id
        self.preview_paused = False
        return self.state()

    def pause(self):
        self.preview_paused = True
        return self.state()

    def stop(self):
        self.preview_active = None
        self.preview_paused = False
        return self.state()


class PreviewHandler(DocReaderHandler):
    def do_GET(self):
        if self.path == "/__workspace_preview__":
            self._send_json({"isolated": True, "playback": "simulated"})
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/native/"):
            self._send_json({"ok": False, "error": "Native actions are disabled in this isolated preview."}, status=400)
            return
        super().do_POST()

    def log_message(self, *_args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18766)
    args = parser.parse_args()
    speech = ThreadingHTTPServer(("127.0.0.1", 0), PreviewSpeech)
    speech_url = f"http://127.0.0.1:{speech.server_port}"
    threading.Thread(target=speech.serve_forever, daemon=True).start()
    os.environ.update({
        "DOC_READER_WEB_SPEECH_BACKEND": "local-kokoro",
        "DOC_READER_TTS_MAC_URL": speech_url,
        "DOC_READER_TTS_UMBRA_URL": speech_url,
        "DOC_READER_STT_URL": speech_url,
        "DOC_READER_ANALYSIS_ENABLED": "0",
        "DOC_READER_ANALYSIS_BACKEND": "heuristic",
    })
    with tempfile.TemporaryDirectory(prefix="read-docs-workspace-preview-") as directory:
        reader = PreviewReader(Path(directory))
        for item_id, kind, title, text in [
            ("reading", "text", "A little room to think", "The first light moves slowly across the room. A book lies open on the table, a few lines underlined in pencil.\n\nThere is something useful about hearing a thought aloud. The pauses become clearer. A sentence that looked finished on the page might still need a little room to breathe.\n\nLeave the window open. Read one more page."),
            ("dictation", "dictation", "Notes for tomorrow", "Pick up where we left off. Keep the useful parts, make a little space, and listen again."),
        ]:
            reader.upsert_library_item({"source": "design-qa", "source_item_id": item_id,
                                        "kind": kind, "title": title, "text": text})
        server = DocReaderHTTPServer(("127.0.0.1", args.port), PreviewHandler, reader)

        def shutdown(*_args):
            threading.Thread(target=server.shutdown, daemon=True).start()

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)
        print(f"Isolated Read Docs preview: http://127.0.0.1:{args.port}", flush=True)
        try:
            server.serve_forever()
        finally:
            reader.shutdown()
            server.server_close()
            speech.shutdown()
            speech.server_close()


if __name__ == "__main__":
    main()
