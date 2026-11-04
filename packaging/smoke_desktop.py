"""Verify dependencies and service startup with an isolated writable profile."""
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

for name in ("kokoro", "faster_whisper", "torch", "spacy", "en_core_web_sm", "pypdf", "docx", "soundfile"):
    importlib.import_module(name)
from doc_reader.platform_tools import find_tool, configure_espeak
assert Path(find_tool("ffmpeg")).is_file()
configure_espeak()
if sys.platform == "win32":
    for name in ("PySide6", "pynput", "sounddevice"):
        importlib.import_module(name)
with tempfile.TemporaryDirectory(prefix="doc-reader-desktop-test-") as profile:
    for module in ("webapp", "tts_service"):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = dict(os.environ, DOC_READER_MANAGED_ROOT=profile, PYTHONDONTWRITEBYTECODE="1",
                   DOC_READER_KOKORO_PRELOAD="0", DOC_READER_STT_PRELOAD="0")
        command = [sys.executable, "-m", f"doc_reader.{module}", "--host", "127.0.0.1", "--port", str(port)]
        if module == "tts_service":
            command += ["--engines", "whisper", "--device", "cpu"]
        process = subprocess.Popen(command, env=env, cwd=profile)
        try:
            for attempt in range(80):
                if process.poll() is not None:
                    raise RuntimeError(f"{module} exited: {process.returncode}")
                try:
                    with urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as response:
                        health = json.load(response)
                    assert health["ok"]
                    if module == "tts_service":
                        assert health["engines"]["whisper"]["available"]
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                raise RuntimeError(f"{module} health timed out")
        finally:
            process.terminate()
            process.wait(timeout=20)
print("PASS: bundled imports, FFmpeg, eSpeak, isolated web and speech health")
