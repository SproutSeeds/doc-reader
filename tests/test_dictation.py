from __future__ import annotations

import io
import math
import struct
import tempfile
import threading
import unittest
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from doc_reader import tts_service, webapp
from doc_reader.http_safety import MAX_UPLOAD_BYTES, read_body, validate_browser_write


def wav_audio(*, silent: bool = False) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16000)
        writer.writeframes(b"".join(
            struct.pack("<h", 0 if silent else int(8000 * math.sin(i / 10)))
            for i in range(16000)
        ))
    return buffer.getvalue()


def segment(text: str = "Recorded words", **confidence):
    return SimpleNamespace(
        text=text, start=0.0, end=1.0, words=[],
        **({"avg_logprob": -0.2, "no_speech_prob": 0.1, "compression_ratio": 1.1} | confidence),
    )


class FakeWhisper:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def transcribe(self, filename, **kwargs):
        self.calls.append(kwargs)
        return iter(self.responses.pop(0)), SimpleNamespace(language="en", duration=1.0)


class DictationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict("os.environ", {"DOC_READER_ANALYSIS_ENABLED": "0"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.reader = webapp.ReaderService(Path(self.temp.name))
        self.reader.state = lambda: {}

    def test_heartbeat_cannot_overwrite_an_enable_toggle(self):
        self.reader.update_settings({"stt_enabled": False})
        loaded = threading.Event()
        release = threading.Event()
        user_finished = threading.Event()
        read = self.reader._settings

        def paused_read():
            settings = read()
            if threading.current_thread().name.startswith("heartbeat") and not loaded.is_set():
                loaded.set()
                release.wait(2)
            return settings

        self.reader._settings = paused_read
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="heartbeat") as heartbeat_pool:
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="user") as user_pool:
                heartbeat = heartbeat_pool.submit(self.reader.update_native_dictation_status, {"recording": False})
                self.assertTrue(loaded.wait(1))

                def enable():
                    self.reader.update_settings({"stt_enabled": True})
                    user_finished.set()

                user = user_pool.submit(enable)
                user_finished.wait(0.1)
                release.set()
                heartbeat.result(timeout=2)
                user.result(timeout=2)
        self.assertTrue(self.reader.native_status()["stt"]["enabled"])

    def test_settings_and_meter_updates_are_atomic_under_load(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = []
            for i in range(40):
                futures.append(pool.submit(self.reader.update_settings, {"stt_enabled": True, "read_rate": 205}))
                futures.append(pool.submit(self.reader.update_native_dictation_status, {"audio_level": i / 40}))
            for future in futures:
                future.result(timeout=5)
        settings = self.reader._settings()
        self.assertTrue(settings["stt_enabled"])
        self.assertEqual(settings["read_rate"], 205)

    def test_heartbeat_never_probes_speech_services(self):
        with patch.object(webapp, "_service_health", side_effect=AssertionError("network probe")):
            result = self.reader.update_native_dictation_status({"recording": True})
        self.assertTrue(result["stt"]["microphone"]["recording"])

    def test_false_string_does_not_enable_recording(self):
        self.reader.update_settings({"stt_enabled": False})
        with self.assertRaises(ValueError):
            self.reader.update_settings({"stt_enabled": "false"})
        self.assertFalse(self.reader._stt_enabled())

    def test_cross_site_pages_cannot_change_dictation_settings(self):
        for headers in (
            {"Host": "127.0.0.1:8766", "Origin": "https://example.com"},
            {"Host": "127.0.0.1:8766", "Origin": "null"},
            {"Host": "127.0.0.1:8766", "Sec-Fetch-Site": "cross-site"},
        ):
            with self.subTest(headers=headers), self.assertRaises(PermissionError):
                validate_browser_write(headers)
        validate_browser_write({"Host": "127.0.0.1:8766", "Origin": "http://127.0.0.1:8766"})
        validate_browser_write({"Host": "doc-reader.example.ts.net", "Origin": "https://doc-reader.example.ts.net"})
        validate_browser_write({"Host": "127.0.0.1:8766"})

    def test_invalid_or_excessive_upload_length_is_rejected_before_read(self):
        for length in ("-1", "invalid", str(MAX_UPLOAD_BYTES + 1)):
            handler = SimpleNamespace(headers={"Content-Length": length}, rfile=None)
            with self.subTest(length=length), self.assertRaises(ValueError):
                read_body(handler)
        with self.assertRaisesRegex(ValueError, "complete request body"):
            read_body(SimpleNamespace(headers={"Content-Length": "12"}, rfile=io.BytesIO(b"short")))
        with self.assertRaisesRegex(ValueError, "chunked"):
            read_body(SimpleNamespace(headers={"Transfer-Encoding": "chunked"}, rfile=None))

    def test_system_default_survives_device_heartbeats(self):
        self.reader.update_settings({"microphone_id": ""})
        result = self.reader.update_native_dictation_status({
            "devices": [{"id": "headset", "name": "Logi USB Headset"}],
        })
        microphone = result["stt"]["microphone"]
        self.assertEqual(microphone["selected_id"], "")
        self.assertIn({"id": "", "name": "System Default"}, microphone["devices"])

    def test_disconnected_selection_is_retained_and_identified(self):
        self.reader.update_settings({"microphone_id": "unplugged"})
        result = self.reader.update_native_dictation_status({
            "devices": [{"id": "headset", "name": "Logi USB Headset"}],
        })
        microphone = result["stt"]["microphone"]
        self.assertEqual(microphone["selected_id"], "unplugged")
        self.assertEqual(microphone["selected_name"], "Disconnected microphone")

    def test_stale_helper_does_not_claim_active_capture(self):
        self.reader.update_native_dictation_status({
            "recording": True, "recording_finish_pending": True, "transcribing": True, "audio_level": 0.8,
        })
        settings = self.reader._settings()
        settings["native_dictation_status_at"] = 1
        self.reader._save_settings(settings)
        microphone = self.reader.native_status()["stt"]["microphone"]
        self.assertFalse(microphone["native_helper_online"])
        self.assertFalse(microphone["recording"])
        self.assertFalse(microphone["recording_finish_pending"])
        self.assertFalse(microphone["transcribing"])
        self.assertEqual(microphone["audio_level"], 0)

    def test_reset_clears_pending_capture_and_transcription(self):
        self.reader.update_native_dictation_status({"recording_finish_pending": True, "transcribing": True})
        self.reader._clear_native_helper_runtime_status("reset")
        self.assertFalse(self.reader._settings()["recording_finish_pending"])
        self.assertFalse(self.reader._settings()["transcribing"])

    def transcribe(self, responses, *, retry=True, silent=False):
        registry = tts_service.EngineRegistry(enabled_engines={"whisper"}, device="cpu")
        model = FakeWhisper(responses)
        with patch.object(registry, "_load_whisper", return_value=model):
            result = registry.transcribe(audio=wav_audio(silent=silent), retry_without_vad=retry)
        return result, model.calls

    def test_vad_recovery_is_bounded_and_marked_for_review(self):
        result, calls = self.transcribe([[], [segment()]])
        self.assertEqual(result.text, "Recorded words")
        self.assertTrue(result.vad_retry)
        self.assertTrue(result.requires_review)
        self.assertEqual([call["vad_filter"] for call in calls], [True, False])
        self.assertFalse(calls[1]["condition_on_previous_text"])

    def test_successful_vad_transcript_is_not_retried(self):
        result, calls = self.transcribe([[segment()]])
        self.assertEqual(len(calls), 1)
        self.assertFalse(result.requires_review)

    def test_silence_is_not_retried(self):
        result, calls = self.transcribe([[]], silent=True)
        self.assertEqual(result.text, "")
        self.assertEqual(len(calls), 1)

    def test_uploads_do_not_retry_unless_requested(self):
        result, calls = self.transcribe([[]], retry=False)
        self.assertEqual(result.text, "")
        self.assertEqual(len(calls), 1)

    def test_low_confidence_recovery_is_rejected(self):
        for confidence in ({"avg_logprob": -2}, {"no_speech_prob": 0.9}, {"compression_ratio": 4}):
            with self.subTest(confidence=confidence):
                result, _ = self.transcribe([[], [segment(**confidence)]])
                self.assertEqual(result.text, "")
                self.assertFalse(result.requires_review)

    def test_recovered_transcript_is_saved_with_review_metadata(self):
        with patch.object(webapp, "_normalize_stt_audio", return_value=(b"audio", "audio/wav", {})), \
             patch.object(webapp, "_require_stt_service", return_value=("mac-whisper", {"url": "http://127.0.0.1:8772"})), \
             patch.object(webapp, "_transcribe_on_stt_service", return_value={"text": "Recovered words", "requires_review": True}) as transcribe:
            result = self.reader.transcribe_audio(b"audio")
        self.assertTrue(transcribe.call_args.kwargs["retry_without_vad"])
        self.assertTrue(result["requires_review"])
        self.assertTrue(result["item"]["source_meta"]["transcription_requires_review"])


if __name__ == "__main__":
    unittest.main()
