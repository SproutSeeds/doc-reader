from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Protocol


class Speaker(Protocol):
    def speak(self, text: str) -> None:
        ...

    def close(self) -> None:
        ...


@dataclass
class ConsoleSpeaker:
    def speak(self, text: str) -> None:
        print(text)

    def close(self) -> None:
        return


class MacSaySpeaker:
    def __init__(self, *, rate: int = 180, voice_hint: str | None = None) -> None:
        if sys.platform != "darwin":
            raise RuntimeError("Mac 'say' backend is only available on macOS.")

        self.say_bin = shutil.which("say")
        if not self.say_bin:
            raise RuntimeError("macOS 'say' command was not found.")

        self.rate = max(90, min(rate, 500))
        self.voice = self._resolve_voice(voice_hint)
        self._active: subprocess.Popen[str] | None = None

    def _resolve_voice(self, voice_hint: str | None) -> str | None:
        if not voice_hint:
            return None

        hint = voice_hint.strip().lower()
        if not hint:
            return None

        try:
            raw = subprocess.check_output(
                [self.say_bin, "-v", "?"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception:  # noqa: BLE001
            return voice_hint

        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if hint in stripped.lower():
                return stripped.split()[0]

        return voice_hint

    def speak(self, text: str) -> None:
        if not text:
            return

        args = [self.say_bin, "-r", str(self.rate)]
        if self.voice:
            args.extend(["-v", self.voice])
        args.append(text)

        self._active = subprocess.Popen(args, text=True)
        self._active.wait()
        self._active = None

    def close(self) -> None:
        if self._active and self._active.poll() is None:
            self._active.terminate()
        self._active = None


class Pyttsx3Speaker:
    def __init__(self, *, rate: int = 180, voice_hint: str | None = None) -> None:
        try:
            import pyttsx3
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Speech backend requires pyttsx3. Install it with: pip install pyttsx3"
            ) from exc

        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)
        if voice_hint:
            self._select_voice(voice_hint)

    def _select_voice(self, voice_hint: str) -> None:
        voice_hint = voice_hint.lower()
        voices = self.engine.getProperty("voices")
        for voice in voices:
            voice_blob = f"{voice.id} {getattr(voice, 'name', '')}".lower()
            if voice_hint in voice_blob:
                self.engine.setProperty("voice", voice.id)
                return

    def speak(self, text: str) -> None:
        if not text:
            return
        self.engine.say(text)
        self.engine.runAndWait()

    def close(self) -> None:
        self.engine.stop()


class ElevenLabsSpeaker:
    def __init__(
        self,
        *,
        api_key: str | None,
        voice_id: str | None,
        model_id: str = "eleven_multilingual_v2",
        output_format: str = "mp3_44100_128",
        request_timeout_seconds: float = 120.0,
    ) -> None:
        try:
            import requests
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "ElevenLabs backend requires requests. Install with: pip install requests"
            ) from exc

        resolved_key = (api_key or os.getenv("ELEVENLABS_API_KEY") or "").strip()
        resolved_voice = (voice_id or os.getenv("ELEVENLABS_VOICE_ID") or "").strip()

        if not resolved_key:
            raise RuntimeError(
                "ElevenLabs API key missing. Set ELEVENLABS_API_KEY or pass --elevenlabs-api-key."
            )
        if not resolved_voice:
            raise RuntimeError(
                "ElevenLabs voice id missing. Set ELEVENLABS_VOICE_ID or pass --elevenlabs-voice-id."
            )

        self.requests = requests
        self.api_key = resolved_key
        self.voice_id = resolved_voice
        self.model_id = model_id
        self.output_format = output_format
        self.timeout = max(10.0, request_timeout_seconds)
        self._player = self._resolve_player()

    def _resolve_player(self) -> list[str]:
        afplay = shutil.which("afplay")
        if afplay:
            return [afplay]

        ffplay = shutil.which("ffplay")
        if ffplay:
            return [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet"]

        raise RuntimeError("No audio player found. Install ffplay or use macOS afplay.")

    def speak(self, text: str) -> None:
        if not text:
            return

        temp_audio_path: str | None = None

        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"
            headers = {
                "xi-api-key": self.api_key,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            }
            params = {"output_format": self.output_format}
            payload = {
                "text": text,
                "model_id": self.model_id,
            }

            with self.requests.post(
                url,
                headers=headers,
                params=params,
                json=payload,
                stream=True,
                timeout=(10.0, self.timeout),
            ) as response:
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"ElevenLabs request failed ({response.status_code}): "
                        f"{_extract_error_message(response)}"
                    )

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as handle:
                    temp_audio_path = handle.name
                    for chunk in response.iter_content(chunk_size=16384):
                        if chunk:
                            handle.write(chunk)

            if not temp_audio_path or not os.path.exists(temp_audio_path):
                raise RuntimeError("ElevenLabs returned no audio data.")

            command = [*self._player, temp_audio_path]
            subprocess.run(command, check=True)

        except self.requests.RequestException as exc:
            raise RuntimeError(f"ElevenLabs network error: {exc}") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Audio playback failed with exit code {exc.returncode}") from exc
        finally:
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                except OSError:
                    pass

    def close(self) -> None:
        return


def _extract_error_message(response) -> str:
    try:
        payload = response.json()
    except ValueError:
        body = (response.text or "").strip()
        return body[:200] if body else "Unknown error"

    if isinstance(payload, dict):
        # ElevenLabs often returns {"detail": {...}} or {"detail": "..."}
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, dict):
            message = detail.get("message")
            if isinstance(message, str):
                return message
            return json.dumps(detail)[:200]
        return json.dumps(payload)[:200]

    return str(payload)[:200]


def build_speaker(
    *,
    rate: int = 180,
    voice_hint: str | None = None,
    backend: str = "auto",
    elevenlabs_api_key: str | None = None,
    elevenlabs_voice_id: str | None = None,
    elevenlabs_model_id: str = "eleven_multilingual_v2",
    elevenlabs_output_format: str = "mp3_44100_128",
) -> Speaker:
    normalized_backend = backend.strip().lower()
    if normalized_backend not in {"auto", "macsay", "pyttsx3", "elevenlabs"}:
        raise RuntimeError(
            "Unknown speech backend. Use one of: auto, macsay, pyttsx3, elevenlabs"
        )

    errors: list[str] = []

    if normalized_backend == "elevenlabs":
        return ElevenLabsSpeaker(
            api_key=elevenlabs_api_key,
            voice_id=elevenlabs_voice_id,
            model_id=elevenlabs_model_id,
            output_format=elevenlabs_output_format,
        )

    if normalized_backend == "macsay":
        return MacSaySpeaker(rate=rate, voice_hint=voice_hint)

    if normalized_backend == "pyttsx3":
        return Pyttsx3Speaker(rate=rate, voice_hint=voice_hint)

    # Auto mode: prefer ElevenLabs if credentials are present, then local backends.
    resolved_key = (elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY") or "").strip()
    resolved_voice = (elevenlabs_voice_id or os.getenv("ELEVENLABS_VOICE_ID") or "").strip()
    if resolved_key and resolved_voice:
        try:
            return ElevenLabsSpeaker(
                api_key=resolved_key,
                voice_id=resolved_voice,
                model_id=elevenlabs_model_id,
                output_format=elevenlabs_output_format,
            )
        except RuntimeError as exc:
            errors.append(str(exc))

    if sys.platform == "darwin":
        try:
            return MacSaySpeaker(rate=rate, voice_hint=voice_hint)
        except RuntimeError as exc:
            errors.append(str(exc))

    try:
        return Pyttsx3Speaker(rate=rate, voice_hint=voice_hint)
    except RuntimeError as exc:
        errors.append(str(exc))

    raise RuntimeError("No speech backend available. " + " | ".join(errors))
