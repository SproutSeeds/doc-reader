from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import tempfile
import uuid
from dataclasses import dataclass, asdict
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import unquote

from .speech import (
    DEFAULT_TTS_MAC_URL,
    DEFAULT_TTS_UMBRA_URL,
    OPENAI_TTS_INSTRUCTIONS,
    OPENAI_TTS_MODEL,
    OPENAI_TTS_RESPONSE_FORMAT,
    OPENAI_TTS_VOICE,
    resolve_openai_api_key,
)

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown"}
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766
DEFAULT_RATE = 180
CHUNK_START_RE = re.compile(r"^\[doc-reader\]\s+chunk-start\s+index=(\d+)\s*$")
CHUNK_DONE_RE = re.compile(r"^\[doc-reader\]\s+chunk-done\s+index=(\d+)\s*$")
NATIVE_HELPER_LABEL = "com.docreader.tray"
NATIVE_HELPER_STALE_SECONDS = 8.0
SPEECH_BACKENDS = {
    "tailscale-4090": "Strict 4090 (Kokoro)",
    "auto": "Local fallback",
    "tailscale-chatterbox": "4090 Chatterbox (experimental)",
    "tailscale-kokoro": "4090 Kokoro",
    "local-kokoro": "Mac Kokoro",
    "macsay": "macOS Voice",
    "openai": "OpenAI API",
}
DEFAULT_STT_ENABLED = False


@dataclass
class HistoryItem:
    id: str
    kind: str
    title: str
    source_path: str
    snippet: str
    created_at: float
    updated_at: float
    last_seconds: float = 0.0
    resume_chunk_index: int = 0
    completed: bool = False


class ReaderService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.upload_dir = root / "web-documents"
        self.text_dir = root / "web-text"
        self.service_inbox_dir = root / "service-inbox"
        self.recordings_dir = root / "dictation-recordings"
        self.history_path = root / "web-history.json"
        self.settings_path = root / "web-settings.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.text_dir.mkdir(parents=True, exist_ok=True)
        self.service_inbox_dir.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._process: subprocess.Popen[str] | None = None
        self._active_id: str | None = None
        self._paused_id: str | None = None
        self._active_chunk_index: int | None = None
        self._last_completed_chunk_index = -1
        self._resume_chunk_index = 0
        self._start_time: float | None = None
        self._start_offset_seconds = 0.0
        self._last_position_seconds = 0.0
        self._status = "Ready."
        self._last_reader_error: str | None = None
        self._suppress_exit_status_for_pid: int | None = None

    def state(self) -> dict[str, Any]:
        with self._lock:
            items = self._items()
            readings = [self._item_payload(item) for item in items if not _is_dictation_item(item)]
            dictations = [self._item_payload(item) for item in items if _is_dictation_item(item)]
            return {
                "ok": True,
                "app": "doc-reader",
                "status": self._status,
                "tts": self.tts_status(),
                "stt": self.stt_status(),
                "running": self._process is not None and self._process.poll() is None,
                "paused": self._process is None and self._paused_id is not None,
                "active_id": self._active_id or self._paused_id,
                "items": readings,
                "readings": readings,
                "dictations": dictations,
            }

    def health(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ok": True,
                "app": "doc-reader",
                "tts": self.tts_status(),
                "stt": self.stt_status(),
                "running": self._process is not None and self._process.poll() is None,
                "paused": self._process is None and self._paused_id is not None,
            }

    def add_text(self, text: str, *, label: str = "Text", kind: str = "text") -> HistoryItem:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("No text to read.")

        item_id = str(uuid.uuid4())
        source_path = self.text_dir / f"{item_id}.txt"
        source_path.write_text(f"{cleaned}\n", encoding="utf-8")
        now = time.time()
        snippet = _snippet(cleaned)
        item = HistoryItem(
            id=item_id,
            kind=kind,
            title=_title(label, snippet),
            source_path=str(source_path),
            snippet=snippet,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            items = self._items()
            items.append(item)
            self._save_items(items)
        return item

    def add_document(self, filename: str, data: bytes) -> HistoryItem:
        safe_name = _safe_filename(filename)
        suffix = Path(safe_name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise ValueError("Unsupported file type.")
        if not data:
            raise ValueError("Uploaded file was empty.")

        item_id = str(uuid.uuid4())
        source_path = self.upload_dir / f"{item_id}-{safe_name}"
        source_path.write_bytes(data)
        now = time.time()
        item = HistoryItem(
            id=item_id,
            kind="document",
            title=safe_name,
            source_path=str(source_path),
            snippet=safe_name,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            items = self._items()
            items.append(item)
            self._save_items(items)
        return item

    def play(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            item = self._find_item(item_id)
            if item is None:
                raise KeyError("History item not found.")
            if not Path(item.source_path).is_file():
                raise FileNotFoundError("Source file not found.")

            if self._process is not None and self._process.poll() is None:
                self._pause_locked()

            if item.completed:
                item.last_seconds = 0.0
                item.resume_chunk_index = 0
                item.completed = False
                self._upsert_item(item)

            resume_chunk = max(0, int(item.resume_chunk_index))
            saved_seconds = max(0.0, float(item.last_seconds))
            start_seconds = 0.0 if resume_chunk > 0 else max(0.0, saved_seconds - 20.0)
            display_seconds = saved_seconds if resume_chunk > 0 else start_seconds

            backend = self._speech_backend()
            args = [
                sys.executable,
                "-m",
                "doc_reader",
                item.source_path,
                "--mode",
                os.getenv("DOC_READER_WEB_MODE", "full"),
                "--style",
                os.getenv("DOC_READER_WEB_STYLE", "balanced"),
                "--rate",
                str(DEFAULT_RATE),
                "--speech-backend",
                backend,
                "--start-chunk-index",
                str(resume_chunk),
                "--start-seconds",
                f"{start_seconds:.2f}",
                "--verbose",
            ]

            env = os.environ.copy()
            package_root = str(Path(__file__).resolve().parents[1])
            env["PYTHONPATH"] = package_root + (
                f":{env['PYTHONPATH']}" if env.get("PYTHONPATH") else ""
            )
            if backend == "openai":
                self._extend_openai_args(args)
                api_key = resolve_openai_api_key()
                if api_key:
                    env["OPENAI_API_KEY"] = api_key
            else:
                env["DOC_READER_AUTO_ALLOW_OPENAI"] = "0"
                env.pop("OPENAI_API_KEY", None)
                env.pop("DOC_READER_OPENAI_API_KEY", None)

            process = subprocess.Popen(
                args,
                cwd=str(self.root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )

            self._process = process
            self._active_id = item.id
            self._paused_id = None
            self._active_chunk_index = None
            self._last_completed_chunk_index = resume_chunk - 1
            self._resume_chunk_index = resume_chunk
            self._last_reader_error = None
            self._start_time = time.monotonic()
            self._start_offset_seconds = display_seconds
            self._last_position_seconds = display_seconds
            self._status = f"Reading {item.title}"
            item.last_seconds = display_seconds
            item.resume_chunk_index = resume_chunk
            item.completed = False
            self._upsert_item(item)

            thread = threading.Thread(
                target=self._watch_process,
                args=(process, item.id),
                name="doc-reader-web-playback",
                daemon=True,
            )
            thread.start()
            return self.state()

    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self._settings()
        backend = payload.get("speech_backend")
        if backend is not None:
            backend = str(backend).strip()
            if backend not in SPEECH_BACKENDS:
                raise ValueError("Unknown speech backend.")
            settings["speech_backend"] = backend
            self._status = f"Voice: {SPEECH_BACKENDS[backend]}"
        if "stt_enabled" in payload:
            settings["stt_enabled"] = bool(payload.get("stt_enabled"))
            self._status = (
                "Dictation hotkey enabled."
                if settings["stt_enabled"]
                else "Dictation hotkey disabled."
            )
        if "microphone_id" in payload:
            settings["microphone_id"] = str(payload.get("microphone_id") or "").strip()
            self._status = "Microphone setting updated."
        self._save_settings(settings)
        return self.state()

    def start_native_helper(self) -> dict[str, Any]:
        if sys.platform != "darwin":
            raise RuntimeError("The native helper is only available on macOS.")
        uid = os.getuid()
        domain = f"gui/{uid}"
        target = f"{domain}/{NATIVE_HELPER_LABEL}"
        plist = Path.home() / "Library" / "LaunchAgents" / f"{NATIVE_HELPER_LABEL}.plist"
        if not plist.exists():
            raise FileNotFoundError("Doc Reader LaunchAgent is not installed.")

        if not _launch_agent_loaded(target):
            subprocess.run(
                ["/bin/launchctl", "bootstrap", domain, str(plist)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        subprocess.run(
            ["/bin/launchctl", "enable", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        result = subprocess.run(
            ["/bin/launchctl", "kickstart", "-k", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            message = (result.stderr or "Could not start Doc Reader app helper.").strip()
            raise RuntimeError(message)
        with self._lock:
            self._status = "Doc Reader app helper started."
        return self.state()

    def update_native_dictation_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self._settings()
        devices = payload.get("devices")
        if isinstance(devices, list):
            sanitized = []
            for device in devices:
                if not isinstance(device, dict):
                    continue
                device_id = str(device.get("id") or "").strip()
                name = str(device.get("name") or "").strip()
                if device_id and name:
                    sanitized.append({"id": device_id, "name": name})
            settings["microphones"] = sanitized
        for key in [
            "microphone_authorization",
            "input_monitoring_trusted",
            "accessibility_trusted",
            "active_microphone_id",
            "recording",
            "recording_start_pending",
            "last_dictation_event",
            "audio_level",
            "audio_peak_level",
            "last_recording_path",
            "last_recording_bytes",
            "last_recording_seconds",
            "last_recording_content_type",
            "last_recording_peak_level",
            "last_recording_created_at",
        ]:
            if key in payload:
                settings[key] = payload.get(key)
        settings["native_dictation_status_at"] = time.time()
        self._save_settings(settings)
        return {"ok": True, "stt": self.stt_status()}

    def tts_status(self) -> dict[str, Any]:
        backend = self._speech_backend()
        return {
            "backend": backend,
            "label": SPEECH_BACKENDS.get(backend, backend),
            "options": [
                {"value": value, "label": label}
                for value, label in SPEECH_BACKENDS.items()
            ],
            "services": {
                "umbra": _service_health(_env("DOC_READER_TTS_UMBRA_URL", DEFAULT_TTS_UMBRA_URL)),
                "mac": _service_health(_env("DOC_READER_TTS_MAC_URL", DEFAULT_TTS_MAC_URL)),
            },
        }

    def stt_status(self) -> dict[str, Any]:
        service = _service_health(_env("DOC_READER_TTS_UMBRA_URL", DEFAULT_TTS_UMBRA_URL))
        engines = service.get("engines", {}) if isinstance(service, dict) else {}
        whisper = engines.get("whisper", {}) if isinstance(engines, dict) else {}
        settings = self._settings()
        return {
            "enabled": self._stt_enabled(),
            "hotkey": "Option",
            "backend": "tailscale-4090-whisper",
            "label": "4090 Whisper",
            "service": service,
            "microphone": _microphone_payload(settings),
            "ready": bool(service.get("ok")) and bool(whisper.get("enabled")),
            "loaded": bool(whisper.get("loaded")),
            "error": whisper.get("error", "") if isinstance(whisper, dict) else "",
        }

    def transcribe_audio(
        self,
        audio: bytes,
        *,
        content_type: str = "audio/wav",
        elapsed_seconds: float | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        if not self._stt_enabled():
            raise PermissionError("Dictation hotkey is disabled.")
        if not audio:
            raise ValueError("No audio to transcribe.")

        started = time.perf_counter()
        normalized_audio, normalized_content_type, normalization = _normalize_stt_audio(
            audio,
            content_type=content_type,
            elapsed_seconds=elapsed_seconds,
        )
        result = _transcribe_on_umbra(
            normalized_audio,
            content_type=normalized_content_type,
            language=language,
        )
        result["normalization"] = normalization
        text = str(result.get("text") or "").strip()
        item_payload = None
        if text:
            item = self.add_text(text, label="Dictation", kind="dictation")
            item_payload = self._item_payload(item)
        with self._lock:
            self._status = (
                f"Dictation transcribed in {time.perf_counter() - started:.1f}s."
                if text
                else "Dictation produced no text."
            )
        return {
            "ok": True,
            "text": text,
            "item": item_payload,
            "transcription": result,
            "state": self.state(),
        }

    def pause(self) -> dict[str, Any]:
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                self._status = "Nothing is currently playing."
                return self.state()
            self._pause_locked()
            return self.state()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._stop_locked(save_progress=True)
            self._active_id = None
            self._paused_id = None
            self._status = "Stopped."
            return self.state()

    def shutdown(self) -> None:
        with self._lock:
            self._stop_locked(save_progress=True)
            self._active_id = None
            self._paused_id = None

    def drain_service_inbox(self) -> int:
        files = sorted(
            self.service_inbox_dir.glob("*.txt"),
            key=lambda path: path.stat().st_mtime if path.exists() else 0,
        )
        latest_item: HistoryItem | None = None
        drained = 0
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
                item = self.add_text(text, label="Highlighted Text")
                path.unlink(missing_ok=True)
            except OSError:
                continue
            except ValueError:
                path.unlink(missing_ok=True)
                continue
            latest_item = item
            drained += 1
        if latest_item is not None:
            self.play(latest_item.id)
        return drained

    def _pause_locked(self) -> None:
        if self._process is None:
            return
        item_id = self._active_id
        self._save_active_progress_locked()
        self._stop_locked(save_progress=False)
        self._active_id = None
        self._paused_id = item_id
        title = self._find_item(item_id).title if item_id and self._find_item(item_id) else "reading"
        self._status = f"Paused {title}"

    def _stop_locked(self, *, save_progress: bool) -> None:
        process = self._process
        if process is None:
            return
        if save_progress:
            self._save_active_progress_locked()
        self._suppress_exit_status_for_pid = process.pid
        _terminate_process_group(process)
        self._process = None
        self._start_time = None

    def _watch_process(self, process: subprocess.Popen[str], item_id: str) -> None:
        code: int | None = None
        try:
            if process.stdout is not None:
                for raw_line in process.stdout:
                    line = raw_line.strip()
                    if line:
                        self._handle_reader_line(line)
            code = process.wait()
        finally:
            with self._lock:
                if self._process is process:
                    completed = process.returncode == 0 or code == 0
                    item = self._find_item(item_id)
                    if item is not None:
                        self._save_active_progress_locked(item=item, completed=completed)
                    self._process = None
                    self._active_id = None
                    self._paused_id = None
                    self._start_time = None
                    if self._suppress_exit_status_for_pid == process.pid:
                        self._suppress_exit_status_for_pid = None
                    else:
                        self._status = "Ready." if completed else (self._last_reader_error or "Reader stopped.")

    def _handle_reader_line(self, line: str) -> None:
        with self._lock:
            match = CHUNK_START_RE.match(line)
            if match:
                index = int(match.group(1))
                self._active_chunk_index = index
                self._resume_chunk_index = max(0, index)
                return

            match = CHUNK_DONE_RE.match(line)
            if match:
                index = int(match.group(1))
                self._last_completed_chunk_index = max(self._last_completed_chunk_index, index)
                if self._active_chunk_index == index:
                    self._active_chunk_index = None
                self._resume_chunk_index = max(self._resume_chunk_index, index + 1)
                self._save_active_progress_locked()
                return

            if _is_reader_error_line(line):
                self._last_reader_error = line
                self._status = line
                return

            if not line.startswith("[doc-reader] page number="):
                self._status = line

    def _save_active_progress_locked(
        self,
        *,
        item: HistoryItem | None = None,
        completed: bool | None = None,
    ) -> None:
        target = item
        if target is None:
            target = self._find_item(self._active_id or self._paused_id)
        if target is None:
            return
        target.last_seconds = self._current_position_seconds_locked()
        target.resume_chunk_index = max(
            0,
            self._active_chunk_index
            if self._active_chunk_index is not None
            else max(self._resume_chunk_index, self._last_completed_chunk_index + 1),
        )
        if completed is not None:
            target.completed = completed
        target.updated_at = time.time()
        self._upsert_item(target)

    def _current_position_seconds_locked(self) -> float:
        if self._process is not None and self._process.poll() is None and self._start_time is not None:
            self._last_position_seconds = self._start_offset_seconds + max(
                0.0,
                time.monotonic() - self._start_time,
            )
        return max(0.0, self._last_position_seconds)

    def _extend_openai_args(self, args: list[str]) -> None:
        model = os.getenv("DOC_READER_OPENAI_MODEL", OPENAI_TTS_MODEL)
        voice = os.getenv("DOC_READER_OPENAI_VOICE", OPENAI_TTS_VOICE)
        response_format = os.getenv("DOC_READER_OPENAI_RESPONSE_FORMAT", OPENAI_TTS_RESPONSE_FORMAT)
        instructions = os.getenv("DOC_READER_OPENAI_INSTRUCTIONS", OPENAI_TTS_INSTRUCTIONS)
        args.extend(["--openai-model", model])
        args.extend(["--openai-voice", voice])
        args.extend(["--openai-response-format", response_format])
        if instructions:
            args.extend(["--openai-instructions", instructions])

    def _items(self) -> list[HistoryItem]:
        try:
            payload = json.loads(self.history_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(payload, list):
            return []
        items: list[HistoryItem] = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            try:
                items.append(HistoryItem(**entry))
            except TypeError:
                continue
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def _save_items(self, items: list[HistoryItem]) -> None:
        deduped = sorted(items, key=lambda item: item.updated_at, reverse=True)[:100]
        temp_path = self.history_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps([asdict(item) for item in deduped], indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.history_path)

    def _find_item(self, item_id: str | None) -> HistoryItem | None:
        if not item_id:
            return None
        for item in self._items():
            if item.id == item_id:
                return item
        return None

    def _upsert_item(self, item: HistoryItem) -> None:
        items = [existing for existing in self._items() if existing.id != item.id]
        items.append(item)
        self._save_items(items)

    def _item_payload(self, item: HistoryItem) -> dict[str, Any]:
        payload = asdict(item)
        payload["playing"] = self._active_id == item.id and self._process is not None
        payload["paused"] = self._paused_id == item.id and self._process is None
        if _is_dictation_item(item):
            payload["text"] = _read_text_file(Path(item.source_path))
        return payload

    def item_text(self, item_id: str) -> dict[str, Any]:
        item = self._find_item(item_id)
        if item is None:
            raise KeyError("History item not found.")
        path = Path(item.source_path)
        if not path.is_file():
            raise FileNotFoundError("Source file not found.")
        if path.suffix.lower() not in {".txt", ".md", ".markdown"} and item.kind != "dictation":
            raise ValueError("History item text is not copyable.")
        return {
            "ok": True,
            "id": item.id,
            "kind": item.kind,
            "text": path.read_text(encoding="utf-8").strip(),
        }

    def last_recording_audio(self) -> tuple[bytes, str]:
        settings = self._settings()
        raw_path = str(settings.get("last_recording_path") or "")
        if not raw_path:
            raise FileNotFoundError("No saved dictation recording yet.")
        path = Path(raw_path).expanduser()
        recordings_dir = self.recordings_dir.resolve()
        try:
            resolved = path.resolve()
        except OSError as exc:
            raise FileNotFoundError("Saved recording is not readable.") from exc
        if recordings_dir not in resolved.parents:
            raise PermissionError("Saved recording is outside the dictation recordings folder.")
        if not resolved.is_file():
            raise FileNotFoundError("Saved recording file not found.")
        content_type = str(settings.get("last_recording_content_type") or "audio/mp4")
        return resolved.read_bytes(), content_type

    def _speech_backend(self) -> str:
        configured = self._settings().get("speech_backend")
        if isinstance(configured, str) and configured in SPEECH_BACKENDS:
            return configured
        env_backend = os.getenv("DOC_READER_WEB_SPEECH_BACKEND", "tailscale-4090")
        return env_backend if env_backend in SPEECH_BACKENDS else "tailscale-4090"

    def _stt_enabled(self) -> bool:
        configured = self._settings().get("stt_enabled")
        if isinstance(configured, bool):
            return configured
        env_value = os.getenv("DOC_READER_STT_ENABLED", "").strip().lower()
        if env_value in {"1", "true", "yes", "on"}:
            return True
        if env_value in {"0", "false", "no", "off"}:
            return False
        return DEFAULT_STT_ENABLED

    def _settings(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_settings(self, settings: dict[str, Any]) -> None:
        temp_path = self.settings_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        temp_path.replace(self.settings_path)


def _is_reader_error_line(line: str) -> bool:
    lowered = line.lower()
    return (
        line.startswith("RuntimeError:")
        or line.startswith("Traceback ")
        or "openai speech request failed" in lowered
        or "insufficient_quota" in lowered
        or "http tts" in lowered
        or "audio playback failed" in lowered
    )


class DocReaderHandler(BaseHTTPRequestHandler):
    server_version = "DocReaderWeb/1.0"

    @property
    def reader(self) -> ReaderService:
        return self.server.reader  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/" or self.path.startswith("/?"):
            self._send_html(INDEX_HTML)
            return
        if self.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        if self.path == "/healthz":
            self._send_json(self.reader.health())
            return
        if self.path == "/api/state":
            self._send_json(self.reader.state())
            return
        if self.path == "/api/dictation/last-recording" or self.path.startswith("/api/dictation/last-recording?"):
            try:
                data, content_type = self.reader.last_recording_audio()
                self._send_binary(data, content_type=content_type)
            except (PermissionError, FileNotFoundError) as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        text_prefix = "/api/items/"
        if self.path.startswith(text_prefix) and self.path.endswith("/text"):
            try:
                item_id = unquote(self.path[len(text_prefix) : -len("/text")])
                self._send_json(self.reader.item_text(item_id))
            except (ValueError, KeyError, FileNotFoundError) as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        try:
            if self.path == "/api/text":
                payload = self._read_json()
                item = self.reader.add_text(
                    str(payload.get("text", "")),
                    label=str(payload.get("label", "Text")),
                )
                self.reader.play(item.id)
                self._send_json(self.reader.state())
                return

            if self.path == "/api/upload":
                filename, data = self._read_upload()
                item = self.reader.add_document(filename, data)
                self.reader.play(item.id)
                self._send_json(self.reader.state())
                return

            if self.path == "/api/pause":
                self._send_json(self.reader.pause())
                return

            if self.path == "/api/stop":
                self._send_json(self.reader.stop())
                return

            if self.path == "/api/settings":
                self._send_json(self.reader.update_settings(self._read_json()))
                return

            if self.path == "/api/native/start":
                self._send_json(self.reader.start_native_helper())
                return

            if self.path == "/api/native/dictation":
                self._send_json(self.reader.update_native_dictation_status(self._read_json()))
                return

            if self.path == "/api/transcribe":
                self._send_json(
                    self.reader.transcribe_audio(
                        self._read_body(),
                        content_type=self.headers.get("Content-Type", "audio/wav"),
                        elapsed_seconds=_optional_float(self.headers.get("X-Doc-Reader-Elapsed-Seconds")),
                        language=_optional_string(self.headers.get("X-Doc-Reader-Language")),
                    )
                )
                return

            play_prefix = "/api/items/"
            if self.path.startswith(play_prefix) and self.path.endswith("/play"):
                item_id = unquote(self.path[len(play_prefix) : -len("/play")])
                self._send_json(self.reader.play(item_id))
                return

            self.send_error(HTTPStatus.NOT_FOUND)
        except PermissionError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.FORBIDDEN)
        except (ValueError, KeyError, FileNotFoundError) as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                {"ok": False, "error": f"Request failed: {exc}"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("[doc-reader-web] " + (format % args) + "\n")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object.")
        return payload

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _read_upload(self) -> tuple[str, bytes]:
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", "0") or "0")
        if "multipart/form-data" not in content_type or length <= 0:
            raise ValueError("Expected a multipart file upload.")

        raw = self.rfile.read(length)
        message = BytesParser(policy=default).parsebytes(
            b"Content-Type: "
            + content_type.encode("utf-8")
            + b"\r\nMIME-Version: 1.0\r\n\r\n"
            + raw
        )
        for part in message.iter_parts():
            disposition = part.get_content_disposition()
            filename = part.get_filename()
            if disposition == "form-data" and filename:
                payload = part.get_payload(decode=True)
                if payload is None:
                    payload = b""
                return filename, payload
        raise ValueError("No uploaded file found.")

    def _send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_binary(self, data: bytes, *, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class DocReaderHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler, reader: ReaderService) -> None:
        super().__init__(server_address, handler)
        self.reader = reader


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except OSError:
        process.terminate()

    deadline = time.monotonic() + 0.9
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)

    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            process.kill()
        process.wait(timeout=0.5)


def _safe_filename(filename: str) -> str:
    cleaned = Path(filename or "document.txt").name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "-", cleaned).strip(" .-")
    return cleaned or "document.txt"


def _snippet(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= 140:
        return collapsed
    return collapsed[:137] + "..."


def _title(label: str, snippet: str) -> str:
    prefix = label.strip() or "Text"
    raw = f"{prefix}: {snippet}" if snippet else prefix
    if len(raw) <= 90:
        return raw
    return raw[:87] + "..."


def _is_dictation_item(item: HistoryItem) -> bool:
    return item.kind == "dictation" or item.title.startswith("Dictation:")


def _launch_agent_loaded(target: str) -> bool:
    result = subprocess.run(
        ["/bin/launchctl", "print", target],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _clamped_float(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return min(maximum, max(minimum, number))


def _microphone_payload(settings: dict[str, Any]) -> dict[str, Any]:
    selected_id = str(settings.get("microphone_id") or "")
    raw_devices = settings.get("microphones")
    status_at = float(settings.get("native_dictation_status_at") or 0.0)
    native_age_seconds = max(0.0, time.time() - status_at) if status_at else None
    native_helper_online = (
        native_age_seconds is not None
        and native_age_seconds <= NATIVE_HELPER_STALE_SECONDS
    )
    devices = [{"id": "", "name": "System Default"}]
    if isinstance(raw_devices, list):
        for device in raw_devices:
            if not isinstance(device, dict):
                continue
            device_id = str(device.get("id") or "").strip()
            name = str(device.get("name") or "").strip()
            if device_id and name:
                devices.append({"id": device_id, "name": name})
    selected_name = "System Default"
    for device in devices:
        if device["id"] == selected_id:
            selected_name = device["name"]
            break
    return {
        "selected_id": selected_id,
        "selected_name": selected_name,
        "active_id": str(settings.get("active_microphone_id") or ""),
        "native_helper_online": native_helper_online,
        "native_status_age_seconds": native_age_seconds,
        "recording": bool(settings.get("recording")),
        "recording_start_pending": bool(settings.get("recording_start_pending")),
        "last_event": str(settings.get("last_dictation_event") or ""),
        "audio_level": _clamped_float(settings.get("audio_level"), 0.0, 1.0),
        "audio_peak_level": _clamped_float(settings.get("audio_peak_level"), 0.0, 1.0),
        "last_recording": {
            "path": str(settings.get("last_recording_path") or ""),
            "bytes": max(0, int(_clamped_float(settings.get("last_recording_bytes"), 0.0, 10_000_000_000.0))),
            "seconds": _clamped_float(settings.get("last_recording_seconds"), 0.0, 86_400.0),
            "content_type": str(settings.get("last_recording_content_type") or "audio/mp4"),
            "peak_level": _clamped_float(settings.get("last_recording_peak_level"), 0.0, 1.0),
            "created_at": _clamped_float(settings.get("last_recording_created_at"), 0.0, 4_102_444_800.0),
        },
        "devices": devices,
        "authorization": str(settings.get("microphone_authorization") or "unknown"),
        "input_monitoring_trusted": bool(settings.get("input_monitoring_trusted")),
        "accessibility_trusted": bool(settings.get("accessibility_trusted")),
    }


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _service_health(base_url: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with urlrequest.urlopen(f"{base_url.rstrip('/')}/healthz", timeout=0.35) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {
            "ok": bool(payload.get("ok")),
            "url": base_url,
            "ms": round((time.perf_counter() - started) * 1000),
            "device": payload.get("device", {}),
            "engines": payload.get("engines", {}),
        }
    except (OSError, ValueError, urlerror.URLError) as exc:
        return {
            "ok": False,
            "url": base_url,
            "ms": round((time.perf_counter() - started) * 1000),
            "error": str(exc),
        }


def _normalize_stt_audio(
    audio: bytes,
    *,
    content_type: str,
    elapsed_seconds: float | None,
) -> tuple[bytes, str, dict[str, Any]]:
    ffmpeg = _local_tool("ffmpeg")
    if not ffmpeg:
        return audio, content_type, {"ok": False, "reason": "ffmpeg unavailable"}

    source_suffix = _suffix_from_content_type(content_type)
    with tempfile.TemporaryDirectory(prefix="doc-reader-stt-") as directory:
        temp_dir = Path(directory)
        source_path = temp_dir / f"input{source_suffix}"
        output_path = temp_dir / "normalized.wav"
        source_path.write_bytes(audio)

        source_duration = _probe_audio_duration(source_path)
        tempo = 1.0
        if elapsed_seconds and elapsed_seconds > 0.25 and source_duration:
            ratio = source_duration / elapsed_seconds
            if 1.15 <= ratio <= 4.0:
                tempo = ratio

        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
        ]
        filters = [
            "highpass=f=80",
            "lowpass=f=7800",
            "loudnorm=I=-18:TP=-2:LRA=7",
        ]
        if abs(tempo - 1.0) >= 0.08:
            filters.insert(0, _atempo_filter(tempo))
        command.extend(["-filter:a", ",".join(filters)])
        command.extend(["-f", "wav", str(output_path)])

        try:
            subprocess.run(command, check=True, capture_output=True, timeout=90)
            normalized = output_path.read_bytes()
        except (OSError, subprocess.SubprocessError) as exc:
            return audio, content_type, {
                "ok": False,
                "reason": f"normalization failed: {exc}",
                "source_duration": source_duration,
                "elapsed_seconds": elapsed_seconds,
                "tempo": tempo,
            }

    if not normalized:
        return audio, content_type, {"ok": False, "reason": "normalization produced no audio"}
    return normalized, "audio/wav", {
        "ok": True,
        "source_content_type": content_type,
        "source_duration": source_duration,
        "elapsed_seconds": elapsed_seconds,
        "tempo": tempo,
        "filters": filters,
    }


def _transcribe_on_umbra(audio: bytes, *, content_type: str, language: str | None = None) -> dict[str, Any]:
    base_url = _env("DOC_READER_TTS_UMBRA_URL", DEFAULT_TTS_UMBRA_URL).rstrip("/")
    headers = {
        "Content-Type": content_type or "audio/wav",
        "X-Doc-Reader-Filename": "dictation.wav",
    }
    stt_language = _optional_string(language) or _env("DOC_READER_STT_LANGUAGE", "en")
    if stt_language:
        headers["X-Doc-Reader-Language"] = stt_language
    request = urlrequest.Request(
        f"{base_url}/v1/audio/transcriptions",
        data=audio,
        method="POST",
        headers=headers,
    )
    try:
        with urlrequest.urlopen(request, timeout=300) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"4090 transcription failed ({exc.code}): {detail}") from exc
    except (OSError, ValueError, urlerror.URLError) as exc:
        raise RuntimeError(f"4090 transcription network error: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("4090 transcription returned an invalid response.")
    if payload.get("ok") is False:
        raise RuntimeError(str(payload.get("error") or "4090 transcription failed."))
    return payload


def _probe_audio_duration(path: Path) -> float | None:
    ffprobe = _local_tool("ffprobe")
    if not ffprobe:
        return None
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return _optional_float(result.stdout)


def _atempo_filter(tempo: float) -> str:
    factors: list[float] = []
    remaining = max(0.5, min(100.0, tempo))
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def _suffix_from_content_type(content_type: str) -> str:
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized in {"audio/mp4", "audio/m4a", "video/mp4"}:
        return ".m4a"
    if normalized in {"audio/aiff", "audio/x-aiff"}:
        return ".aiff"
    if normalized in {"audio/mpeg", "audio/mp3"}:
        return ".mp3"
    return ".wav"


def _local_tool(name: str) -> str:
    candidates = [
        shutil.which(name) or "",
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
        f"/usr/bin/{name}",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


def _optional_string(value: object) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def _optional_float(value: object) -> float | None:
    try:
        parsed = float(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    if not parsed == parsed or parsed <= 0:
        return None
    return parsed


def _env(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


def _managed_root() -> Path:
    value = os.getenv("DOC_READER_MANAGED_ROOT")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".doc-reader-managed"


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Doc Reader</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f7f7f4;
      --panel: #ffffff;
      --ink: #1d1e20;
      --muted: #63676d;
      --line: #d8d9d2;
      --accent: #28666e;
      --accent-ink: #ffffff;
      --success: #16833a;
      --warn: #9a3412;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #191a1d;
        --panel: #23262b;
        --ink: #f2f3f4;
        --muted: #a8adb5;
        --line: #3a3f47;
        --accent: #5aa6b0;
        --accent-ink: #071214;
        --success: #55c979;
        --warn: #f59e0b;
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    main {
      max-width: 1080px;
      margin: 0 auto;
      padding: 24px;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }
    h1 {
      font-size: 24px;
      margin: 0;
      letter-spacing: 0;
    }
    h2 {
      font-size: 13px;
      margin: 0;
      letter-spacing: 0;
      text-transform: uppercase;
      color: var(--muted);
    }
    .status {
      color: var(--muted);
      text-align: right;
      min-width: 180px;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }
    section {
      min-width: 0;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }
    .stack { display: grid; gap: 10px; }
    label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 5px;
    }
    textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: transparent;
      color: var(--ink);
      font: inherit;
    }
    textarea {
      min-height: 180px;
      resize: vertical;
    }
    select {
      min-height: 36px;
      padding: 7px 10px;
    }
    input[type="file"] {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      background: transparent;
      color: var(--ink);
    }
    .check-row {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--ink);
    }
    .check-row label {
      margin: 0;
      color: var(--ink);
      font-size: 13px;
    }
    .row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }
    button {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 11px;
      background: var(--panel);
      color: var(--ink);
      font: inherit;
      min-height: 36px;
      cursor: pointer;
    }
    button.primary {
      background: var(--accent);
      color: var(--accent-ink);
      border-color: var(--accent);
    }
    button.icon-button {
      width: 36px;
      min-width: 36px;
      padding: 0;
      display: inline-grid;
      place-items: center;
      transition: border-color 180ms ease, color 180ms ease, background 180ms ease, opacity 180ms ease;
    }
    button.icon-button svg {
      width: 17px;
      height: 17px;
      stroke: currentColor;
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
      fill: none;
    }
    button.icon-button.copied {
      color: var(--success);
      border-color: var(--success);
      background: color-mix(in srgb, var(--success) 12%, transparent);
    }
    .view-toggle {
      display: grid;
      grid-template-columns: 1fr 1fr;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: var(--panel);
    }
    .view-toggle button {
      border: 0;
      border-radius: 0;
      min-height: 40px;
      background: transparent;
    }
    .view-toggle button + button {
      border-left: 1px solid var(--line);
    }
    .view-toggle button.active {
      background: var(--accent);
      color: var(--accent-ink);
    }
    button:disabled {
      cursor: default;
      opacity: 0.55;
    }
    .history {
      display: grid;
      gap: 10px;
    }
    .list-column {
      display: grid;
      gap: 18px;
    }
    .list-block {
      display: grid;
      gap: 10px;
    }
    .list-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .count {
      color: var(--muted);
      font-size: 12px;
    }
    [hidden] {
      display: none !important;
    }
    .card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px;
      display: grid;
      gap: 8px;
    }
    .card.active {
      border-color: var(--accent);
    }
    .card-top {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
    }
    .title {
      font-weight: 650;
      overflow-wrap: anywhere;
    }
    .meta, .snippet {
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .dictation-text {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: var(--ink);
      font-size: 14px;
    }
    .voice-status {
      color: var(--muted);
      font-size: 12px;
      min-height: 18px;
    }
    .mic-meter {
      --level: 0;
      height: 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--bg);
      overflow: hidden;
    }
    .mic-meter > div {
      width: calc(var(--level) * 100%);
      min-width: 2px;
      max-width: 100%;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--accent), var(--success));
      transition: width 90ms linear;
    }
    .mic-meter.active {
      border-color: color-mix(in srgb, var(--accent) 55%, var(--line));
    }
    .recording-debug {
      display: grid;
      gap: 6px;
      border: 1px solid color-mix(in srgb, var(--accent) 45%, var(--line));
      border-radius: 8px;
      padding: 8px 10px;
      background: color-mix(in srgb, var(--accent) 10%, var(--panel));
      color: var(--muted);
      font-size: 12px;
    }
    .recording-debug[hidden] {
      display: none;
    }
    .recording-debug strong {
      color: var(--fg);
      font-size: 13px;
    }
    .recording-debug audio {
      width: 100%;
      height: 32px;
    }
    .empty {
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 18px;
      text-align: center;
    }
    .error {
      color: var(--warn);
      min-height: 20px;
    }
    @media (max-width: 760px) {
      main { padding: 16px; }
      header { align-items: flex-start; flex-direction: column; }
      .status { text-align: left; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Doc Reader</h1>
      <div class="status" id="status">Ready.</div>
    </header>
    <div class="grid">
      <section class="panel stack">
        <div>
          <label for="file">Document</label>
          <input id="file" type="file" accept=".pdf,.docx,.txt,.md,.markdown">
        </div>
        <div>
          <label for="text">Text</label>
          <textarea id="text"></textarea>
        </div>
        <div>
          <label for="voice">Voice</label>
          <select id="voice"></select>
          <div class="voice-status" id="voiceStatus"></div>
        </div>
        <div>
          <div class="row">
            <div class="check-row">
              <input id="dictationEnabled" type="checkbox">
              <label for="dictationEnabled">Hold Option for 4090 dictation</label>
            </div>
            <button id="startNativeHelper" type="button" hidden>Start Helper</button>
          </div>
          <div class="voice-status" id="dictationStatus"></div>
          <div class="mic-meter" id="dictationMeter" aria-label="Microphone level"><div></div></div>
        </div>
        <div>
          <label for="microphone">Microphone</label>
          <select id="microphone"></select>
          <div class="voice-status" id="microphoneStatus"></div>
        </div>
        <div class="recording-debug" id="dictationRecordingDebug" hidden>
          <strong>Latest Recording</strong>
          <div id="dictationRecordingStatus"></div>
          <audio id="dictationRecordingAudio" controls preload="none"></audio>
        </div>
        <div class="row">
          <button class="primary" id="readText">Read Text</button>
          <button id="pause">Pause</button>
          <button id="stop">Stop</button>
        </div>
        <div class="error" id="error"></div>
      </section>
      <section class="list-column">
        <div class="view-toggle" role="tablist" aria-label="History view">
          <button id="showReadings" type="button" role="tab" aria-controls="readingsBlock">Readings</button>
          <button id="showDictations" type="button" role="tab" aria-controls="dictationsBlock">Dictations</button>
        </div>
        <div class="list-block" id="readingsBlock">
          <div class="list-header">
            <h2>Readings</h2>
            <div class="count" id="readingsCount"></div>
          </div>
          <div class="history" id="readings"></div>
        </div>
        <div class="list-block" id="dictationsBlock">
          <div class="list-header">
            <h2>Dictations</h2>
            <div class="count" id="dictationsCount"></div>
          </div>
          <div class="history" id="dictations"></div>
        </div>
      </section>
    </div>
  </main>
  <script>
    const state = { data: null };
    const statusEl = document.getElementById("status");
    const readingsEl = document.getElementById("readings");
    const dictationsEl = document.getElementById("dictations");
    const readingsCountEl = document.getElementById("readingsCount");
    const dictationsCountEl = document.getElementById("dictationsCount");
    const errorEl = document.getElementById("error");
    const textEl = document.getElementById("text");
    const fileEl = document.getElementById("file");
    const pauseBtn = document.getElementById("pause");
    const stopBtn = document.getElementById("stop");
    const voiceEl = document.getElementById("voice");
    const voiceStatusEl = document.getElementById("voiceStatus");
    const dictationEnabledEl = document.getElementById("dictationEnabled");
    const dictationStatusEl = document.getElementById("dictationStatus");
    const dictationMeterEl = document.getElementById("dictationMeter");
    const dictationRecordingDebugEl = document.getElementById("dictationRecordingDebug");
    const dictationRecordingStatusEl = document.getElementById("dictationRecordingStatus");
    const dictationRecordingAudioEl = document.getElementById("dictationRecordingAudio");
    const startNativeHelperEl = document.getElementById("startNativeHelper");
    const microphoneEl = document.getElementById("microphone");
    const microphoneStatusEl = document.getElementById("microphoneStatus");
    const showReadingsBtn = document.getElementById("showReadings");
    const showDictationsBtn = document.getElementById("showDictations");
    const readingsBlockEl = document.getElementById("readingsBlock");
    const dictationsBlockEl = document.getElementById("dictationsBlock");
    state.activeView = localStorage.getItem("docReader.historyView") || "readings";

    async function api(path, options = {}) {
      const response = await fetch(path, options);
      const raw = await response.text();
      let payload = {};
      if (raw.trim()) {
        try {
          payload = JSON.parse(raw);
        } catch (_error) {
          throw new Error(raw.slice(0, 180) || `HTTP ${response.status}`);
        }
      } else if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || "Request failed.");
      }
      return payload;
    }

    function timeLabel(seconds) {
      const total = Math.max(0, Math.floor(seconds || 0));
      const hours = Math.floor(total / 3600);
      const minutes = Math.floor((total % 3600) / 60);
      const rest = total % 60;
      if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
      return `${minutes}m ${String(rest).padStart(2, "0")}s`;
    }

    function byteLabel(bytes) {
      const value = Math.max(0, Number(bytes || 0));
      if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
      if (value >= 1024) return `${Math.round(value / 1024)} KB`;
      return `${Math.round(value)} B`;
    }

    function render(data) {
      const previousDictationCount = state.data && state.data.dictations
        ? state.data.dictations.length
        : 0;
      state.data = data;
      statusEl.textContent = data.status || "Ready.";
      renderVoice(data.tts || {});
      renderDictation(data.stt || {});
      pauseBtn.disabled = !data.running && !data.paused;
      pauseBtn.textContent = data.paused ? "Resume" : "Pause";
      stopBtn.disabled = !data.running && !data.paused;

      const readings = data.readings || data.items || [];
      const dictations = data.dictations || [];
      if (dictations.length > previousDictationCount) {
        setActiveView("dictations");
      }
      renderReadings(readings);
      renderDictations(dictations);
      renderActiveView(readings.length, dictations.length);
    }

    function setActiveView(view) {
      state.activeView = view === "dictations" ? "dictations" : "readings";
      localStorage.setItem("docReader.historyView", state.activeView);
      const data = state.data || {};
      renderActiveView((data.readings || data.items || []).length, (data.dictations || []).length);
    }

    function renderActiveView(readingsCount, dictationsCount) {
      const showingDictations = state.activeView === "dictations";
      readingsBlockEl.hidden = showingDictations;
      dictationsBlockEl.hidden = !showingDictations;
      showReadingsBtn.classList.toggle("active", !showingDictations);
      showDictationsBtn.classList.toggle("active", showingDictations);
      showReadingsBtn.textContent = `Readings ${readingsCount}`;
      showDictationsBtn.textContent = `Dictations ${dictationsCount}`;
      showReadingsBtn.setAttribute("aria-selected", String(!showingDictations));
      showDictationsBtn.setAttribute("aria-selected", String(showingDictations));
    }

    function renderReadings(items) {
      readingsEl.innerHTML = "";
      readingsCountEl.textContent = countLabel(items.length);
      if (items.length === 0) {
        readingsEl.appendChild(emptyCard("No readings yet."));
        return;
      }

      for (const item of items) {
        readingsEl.appendChild(makeReadingCard(item));
      }
    }

    function renderDictations(items) {
      dictationsEl.innerHTML = "";
      dictationsCountEl.textContent = countLabel(items.length);
      if (items.length === 0) {
        dictationsEl.appendChild(emptyCard("No dictations yet."));
        return;
      }

      for (const item of items) {
        dictationsEl.appendChild(makeDictationCard(item));
      }
    }

    function countLabel(count) {
      return `${count} ${count === 1 ? "card" : "cards"}`;
    }

    function emptyCard(text) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = text;
      return empty;
    }

    function makeReadingCard(item) {
      const card = document.createElement("article");
      card.className = "card" + (item.playing || item.paused ? " active" : "");

      const top = document.createElement("div");
      top.className = "card-top";

      const info = document.createElement("div");
      const title = document.createElement("div");
      title.className = "title";
      title.textContent = item.title;
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = `${item.kind === "document" ? "Document" : "Text"} / ${item.completed ? "Complete" : timeLabel(item.last_seconds)}`;
      info.append(title, meta);

      const play = document.createElement("button");
      play.textContent = item.playing ? "Pause" : (item.paused ? "Resume" : "Play");
      play.className = item.playing || item.paused ? "" : "primary";
      play.addEventListener("click", async () => {
        try {
          errorEl.textContent = "";
          if (item.playing || item.paused) {
            render(await api(item.playing ? "/api/pause" : `/api/items/${encodeURIComponent(item.id)}/play`, { method: "POST" }));
          } else {
            render(await api(`/api/items/${encodeURIComponent(item.id)}/play`, { method: "POST" }));
          }
        } catch (error) {
          errorEl.textContent = error.message;
        }
      });

      top.append(info, play);

      const snippet = document.createElement("div");
      snippet.className = "snippet";
      snippet.textContent = item.snippet || item.source_path || "";
      card.append(top, snippet);
      return card;
    }

    function makeDictationCard(item) {
      const card = document.createElement("article");
      card.className = "card";

      const top = document.createElement("div");
      top.className = "card-top";

      const info = document.createElement("div");
      const title = document.createElement("div");
      title.className = "title";
      title.textContent = item.title;
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = "Dictation";
      info.append(title, meta);

      const copy = document.createElement("button");
      copy.className = "icon-button";
      copy.type = "button";
      copy.title = "Copy dictation";
      copy.setAttribute("aria-label", "Copy dictation");
      copy.innerHTML = icon("copy");
      copy.addEventListener("click", async () => {
        try {
          errorEl.textContent = "";
          const payload = await api(`/api/items/${encodeURIComponent(item.id)}/text`);
          await navigator.clipboard.writeText(payload.text || "");
          showCopied(copy);
        } catch (error) {
          errorEl.textContent = error.message;
        }
      });

      top.append(info, copy);

      const snippet = document.createElement("div");
      snippet.className = "dictation-text";
      snippet.textContent = item.text || item.snippet || "";
      card.append(top, snippet);
      return card;
    }

    function showCopied(button) {
      button.classList.add("copied");
      button.innerHTML = icon("check");
      window.setTimeout(() => {
        button.classList.remove("copied");
        button.innerHTML = icon("copy");
      }, 1100);
    }

    function icon(name) {
      if (name === "check") {
        return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';
      }
      return '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="10" height="10" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1"/></svg>';
    }

    function renderVoice(tts) {
      const current = tts.backend || "auto";
      const options = tts.options || [];
      if (voiceEl.dataset.loaded !== "true") {
        voiceEl.innerHTML = "";
        for (const option of options) {
          const entry = document.createElement("option");
          entry.value = option.value;
          entry.textContent = option.label;
          voiceEl.appendChild(entry);
        }
        voiceEl.dataset.loaded = "true";
      }
      voiceEl.value = current;
      const services = tts.services || {};
      const umbra = services.umbra && services.umbra.ok ? "4090 online" : "4090 offline";
      const mac = services.mac && services.mac.ok ? "Mac neural online" : "Mac neural offline";
      voiceStatusEl.textContent = `${tts.label || current} / ${umbra} / ${mac}`;
    }

    function renderDictation(stt) {
      dictationEnabledEl.checked = !!stt.enabled;
      const service = stt.service || {};
      const serviceLabel = service.ok ? "4090 online" : "4090 offline";
      const modelLabel = stt.loaded ? "model loaded" : (stt.ready ? "model ready" : "model unavailable");
      const mic = stt.microphone || {};
      renderMicrophones(mic);
      const helperLabel = mic.recording
        ? "recording"
        : (mic.recording_start_pending ? "starting recorder" : (mic.native_helper_online ? "helper online" : "start app helper"));
      const inputLabel = mic.input_monitoring_trusted ? "hotkey allowed" : "allow Input Monitoring";
      startNativeHelperEl.hidden = !stt.enabled || !!mic.native_helper_online;
      dictationStatusEl.textContent = `${stt.label || "4090 Whisper"} / ${serviceLabel} / ${modelLabel} / ${helperLabel} / ${inputLabel}`;
      const level = Math.max(0, Math.min(1, Number(mic.audio_level || 0)));
      const peak = Math.max(0, Math.min(1, Number(mic.audio_peak_level || 0)));
      dictationMeterEl.style.setProperty("--level", String(level));
      dictationMeterEl.classList.toggle("active", !!mic.recording || !!mic.recording_start_pending);
      dictationMeterEl.title = `Mic level ${Math.round(level * 100)}%, peak ${Math.round(peak * 100)}%`;
      renderLastRecording(mic.last_recording || {});
    }

    function renderLastRecording(recording) {
      const hasRecording = !!recording.path && Number(recording.bytes || 0) > 0;
      dictationRecordingDebugEl.hidden = !hasRecording;
      if (!hasRecording) {
        dictationRecordingAudioEl.removeAttribute("src");
        dictationRecordingAudioEl.dataset.path = "";
        return;
      }
      const peak = Math.round(Math.max(0, Math.min(1, Number(recording.peak_level || 0))) * 100);
      dictationRecordingStatusEl.textContent =
        `${byteLabel(recording.bytes)} / ${timeLabel(recording.seconds)} / peak ${peak}%`;
      if (dictationRecordingAudioEl.dataset.path !== recording.path) {
        dictationRecordingAudioEl.src = `/api/dictation/last-recording?t=${encodeURIComponent(String(recording.created_at || Date.now()))}`;
        dictationRecordingAudioEl.dataset.path = recording.path;
      }
    }

    function renderMicrophones(mic) {
      const devices = mic.devices || [{ id: "", name: "System Default" }];
      const signature = JSON.stringify(devices);
      if (microphoneEl.dataset.signature !== signature) {
        microphoneEl.innerHTML = "";
        for (const device of devices) {
          const entry = document.createElement("option");
          entry.value = device.id || "";
          entry.textContent = device.name || "System Default";
          microphoneEl.appendChild(entry);
        }
        microphoneEl.dataset.signature = signature;
      }
      microphoneEl.value = mic.selected_id || "";
      const selected = mic.selected_name || "System Default";
      const permission = mic.authorization === "authorized" ? "mic allowed" : `mic ${mic.authorization || "unknown"}`;
      const accessibility = mic.accessibility_trusted ? "paste allowed" : "allow Accessibility";
      const helper = mic.native_helper_online ? "native helper online" : "native helper offline";
      const lastEvent = mic.last_event ? ` / ${mic.last_event}` : "";
      microphoneStatusEl.textContent = `${selected} / ${permission} / ${accessibility} / ${helper}${lastEvent}`;
    }

    async function refresh() {
      try {
        render(await api("/api/state"));
      } catch (error) {
        errorEl.textContent = error.message;
      }
    }

    document.getElementById("readText").addEventListener("click", async () => {
      try {
        errorEl.textContent = "";
        render(await api("/api/text", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ label: "Text", text: textEl.value })
        }));
      } catch (error) {
        errorEl.textContent = error.message;
      }
    });

    fileEl.addEventListener("change", async () => {
      const file = fileEl.files && fileEl.files[0];
      if (!file) return;
      const body = new FormData();
      body.append("file", file);
      try {
        errorEl.textContent = "";
        render(await api("/api/upload", { method: "POST", body }));
      } catch (error) {
        errorEl.textContent = error.message;
      } finally {
        fileEl.value = "";
      }
    });

    pauseBtn.addEventListener("click", async () => {
      try {
        errorEl.textContent = "";
        const paused = state.data && state.data.paused;
        const active = state.data && state.data.active_id;
        render(await api(paused && active ? `/api/items/${encodeURIComponent(active)}/play` : "/api/pause", { method: "POST" }));
      } catch (error) {
        errorEl.textContent = error.message;
      }
    });

    stopBtn.addEventListener("click", async () => {
      try {
        errorEl.textContent = "";
        render(await api("/api/stop", { method: "POST" }));
      } catch (error) {
        errorEl.textContent = error.message;
      }
    });

    voiceEl.addEventListener("change", async () => {
      try {
        errorEl.textContent = "";
        render(await api("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ speech_backend: voiceEl.value })
        }));
      } catch (error) {
        errorEl.textContent = error.message;
      }
    });

    dictationEnabledEl.addEventListener("change", async () => {
      try {
        errorEl.textContent = "";
        render(await api("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ stt_enabled: dictationEnabledEl.checked })
        }));
      } catch (error) {
        errorEl.textContent = error.message;
      }
    });

    microphoneEl.addEventListener("change", async () => {
      try {
        errorEl.textContent = "";
        render(await api("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ microphone_id: microphoneEl.value })
        }));
      } catch (error) {
        errorEl.textContent = error.message;
      }
    });

    startNativeHelperEl.addEventListener("click", async () => {
      try {
        errorEl.textContent = "";
        render(await api("/api/native/start", { method: "POST" }));
      } catch (error) {
        errorEl.textContent = error.message;
      }
    });

    showReadingsBtn.addEventListener("click", () => setActiveView("readings"));
    showDictationsBtn.addEventListener("click", () => setActiveView("dictations"));

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        if (document.activeElement && document.activeElement.blur) {
          document.activeElement.blur();
        }
      }
    });

    refresh();
    setInterval(refresh, 1500);
  </script>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Doc Reader web app.")
    parser.add_argument("--host", default=os.getenv("DOC_READER_WEB_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.getenv("DOC_READER_WEB_PORT", DEFAULT_PORT)))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    reader = ReaderService(_managed_root())
    stop_event = threading.Event()
    server = DocReaderHTTPServer((args.host, args.port), DocReaderHandler, reader)

    def drain_loop() -> None:
        while not stop_event.is_set():
            reader.drain_service_inbox()
            stop_event.wait(1.0)

    threading.Thread(target=drain_loop, name="doc-reader-service-inbox", daemon=True).start()

    def handle_signal(_signum, _frame) -> None:
        stop_event.set()
        reader.shutdown()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    print(f"[doc-reader-web] listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        stop_event.set()
        reader.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
