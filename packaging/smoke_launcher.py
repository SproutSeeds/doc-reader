"""Exercise the installed Windows EXE with no developer tools or user profile.

This deliberately disables microphone capture. Physical input/output and global
shortcut acceptance belong to the user's setup trial on an interactive desktop.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

from doc_reader.platform_tools import pid_is_running


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("launcher", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    assert sys.platform == "win32", "Run this check on Windows"
    launcher = args.launcher.resolve()
    assert launcher.is_file()
    python = launcher.parent / "runtime/python.exe"
    with tempfile.TemporaryDirectory(prefix="read-docs-installed-") as folder:
        profile = Path(folder)
        web_port, speech_port = free_port(), free_port()
        while speech_port == web_port:
            speech_port = free_port()
        web = f"http://127.0.0.1:{web_port}"
        speech = f"http://127.0.0.1:{speech_port}"
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("DOC_READER_") and k not in ("PYTHONPATH", "PYTHONHOME")}
        env.update({
            "PATH": os.pathsep.join((str(Path(os.environ["SystemRoot"]) / "System32"), os.environ["SystemRoot"])),
            "PYTHONNOUSERSITE": "1", "PYTHONSAFEPATH": "1", "PYTHONDONTWRITEBYTECODE": "1",
            "DOC_READER_MANAGED_ROOT": folder, "DOC_READER_WEB_PORT": str(web_port),
            "DOC_READER_WEB_URL": web, "DOC_READER_TTS_PORT": str(speech_port),
            "DOC_READER_TTS_MAC_URL": speech, "DOC_READER_HTTP_TTS_URL": speech,
            "DOC_READER_TTS_UMBRA_URL": "http://127.0.0.1:1",
            "DOC_READER_TTS_DEVICE": "cpu", "DOC_READER_KOKORO_DEVICE": "cpu",
            "DOC_READER_STT_DEVICE": "cpu", "DOC_READER_STT_ENABLED": "0",
            "DOC_READER_DICTATION_PREARM": "0", "DOC_READER_ANALYSIS_ENABLED": "0",
            "HF_HOME": str(profile / "empty-model-cache"), "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        })

        def request(path: str, payload=None):
            data = None if payload is None else json.dumps(payload).encode()
            req = Request(web + path, data=data, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=3) as response:
                return json.load(response)

        def pids() -> dict[str, int]:
            return {path.stem: int(path.read_text().strip()) for path in (profile / "pids").glob("*.pid")}

        def launch() -> float:
            started = time.monotonic()
            process = subprocess.Popen([str(launcher)], cwd=folder, env=env)
            try:
                for attempt in range(240):
                    code = process.poll()
                    if code not in (None, 0):
                        raise RuntimeError(f"Installed launcher failed: {code}")
                    try:
                        healthy = request("/healthz")["ok"]
                        native = request("/api/native/status")
                        with urlopen(speech + "/healthz", timeout=3) as response:
                            speech_ok = json.load(response)["ok"]
                        if healthy and speech_ok and native["stt"]["microphone"]["native_helper_online"]:
                            assert process.wait(timeout=20) == 0
                            assert not native["stt"]["enabled"]
                            assert set(pids()) == {"web", "tts", "helper"}
                            return round(time.monotonic() - started, 2)
                    except OSError:
                        pass
                    time.sleep(.5)
                raise RuntimeError("Installed EXE did not start all three services")
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)

        def stop() -> None:
            owned = pids()
            process = subprocess.Popen([str(launcher), "--stop"], cwd=folder, env=env)
            try:
                assert process.wait(timeout=45) == 0
            finally:
                if process.poll() is None:
                    process.terminate()
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and any(pid_is_running(pid) for pid in owned.values()):
                time.sleep(.2)
            assert not any(pid_is_running(pid) for pid in owned.values()), "Owned services survived shutdown"
            assert not pids(), "Stale service PID files after shutdown"

        try:
            cold_seconds = launch()
            original_pids = pids()
            duplicate_seconds = launch()
            assert pids() == original_pids, "Opening twice created duplicate services"
            preferences = {"dictation_key": "f8", "selection_shortcut": "<ctrl>+<alt>+r", "setup_step": 2}
            request("/api/settings", preferences)
            stop()
            restart_seconds = launch()
            saved = json.loads((profile / "web-settings.json").read_text())
            assert all(saved[name] == value for name, value in preferences.items()), "Preferences did not survive restart"
            stop()
            report = {"status": "PASS", "cold_start_seconds": cold_seconds,
                      "duplicate_open_seconds": duplicate_seconds, "restart_seconds": restart_seconds,
                      "actual_installed_exe": True, "developer_tools_on_path": False,
                      "clean_profile": True, "duplicate_services": False, "preferences_preserved": True,
                      "all_owned_services_stopped": True, "microphone_capture": "disabled",
                      "physical_shortcut_audio_trial": "requires an interactive user"}
            if args.report:
                args.report.write_text(json.dumps(report, indent=2) + "\n")
            print("PASS: installed EXE cold start, duplicate open, saved preferences, restart and shutdown", flush=True)
        except BaseException:
            for path in (profile / "logs").glob("*.log"):
                print(path.name + ":\n" + path.read_text(errors="replace")[-8000:], file=sys.stderr)
            raise
        finally:
            # The ownership marker confines cleanup to this disposable profile.
            subprocess.run([str(python), "-m", "doc_reader.windows_app", "stop"],
                           cwd=folder, env=env, timeout=45, check=True)


if __name__ == "__main__":
    main()
