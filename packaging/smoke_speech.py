"""Exercise the shipped models with a public, synthetic English sentence."""
import os
import sys
from doc_reader.tts_service import EngineRegistry

os.environ.setdefault("DOC_READER_STT_MODEL", "small" if sys.platform == "win32" else "base")
registry = EngineRegistry(enabled_engines={"kokoro", "whisper"}, device="cpu")
audio = registry.synthesize(engine="kokoro", voice="af_heart", text=(
    "Doc Reader reads documents aloud. You can also dictate your thoughts into text."
))
assert audio.audio_seconds > 1 and len(audio.audio) > 1000
result = registry.transcribe(audio=audio.audio, language="en")
print(f"Kokoro: {audio.audio_seconds:.2f}s at {audio.sample_rate}Hz; Whisper: {result.text}", flush=True)
assert all(word in result.text.lower() for word in ("reader", "documents", "dictate"))
print("PASS: actual Kokoro synthesis and Whisper transcription", flush=True)
