from __future__ import annotations

import contextlib
import io
import unittest

from doc_reader import tts_service


class FakeNumpy:
    @staticmethod
    def asarray(audio: object, *, dtype: str) -> tuple[str, object]:
        return dtype, audio


class RecoveringPipeline:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, text: str, *, voice: str, speed: float):  # noqa: ANN201
        self.calls.append(text)
        if len(self.calls) == 1:
            raise RuntimeError(
                "number of lines in input and output must be equal, "
                "we have: input=1, output=3"
            )
        yield text, "phonemes", f"audio:{text}"


class FailingPipeline:
    def __call__(self, text: str, *, voice: str, speed: float):  # noqa: ANN201, ARG002
        raise ValueError("model failed")
        yield  # pragma: no cover


class TTSServiceTests(unittest.TestCase):
    def test_clean_text_replaces_hidden_controls(self) -> None:
        text = "Read\u200bthis\u202e now"

        self.assertEqual(tts_service._clean_text_for_tts(text), "Read this now.")

    def test_kokoro_retry_recovers_from_phonemizer_line_mismatch(self) -> None:
        pipeline = RecoveringPipeline()

        with contextlib.redirect_stderr(io.StringIO()):
            chunks = tts_service._kokoro_audio_chunks_for_segment(
                pipeline,
                "bad:::token\u2705 path",
                voice="af_heart",
                speed=1.0,
                np_module=FakeNumpy,
            )

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], ("float32", "audio:bad token path."))
        self.assertEqual(pipeline.calls, ["bad:::token\u2705 path", "bad token path."])

    def test_kokoro_retry_keeps_non_line_mismatch_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "model failed"):
            tts_service._kokoro_audio_chunks_for_segment(
                FailingPipeline(),
                "hello",
                voice="af_heart",
                speed=1.0,
                np_module=FakeNumpy,
            )


if __name__ == "__main__":
    unittest.main()
