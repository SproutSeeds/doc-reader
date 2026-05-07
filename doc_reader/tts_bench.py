from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_TEXT = (
    "Doc Reader is testing local speech generation across the 4090 and the Mac. "
    "This sample should be long enough to measure latency, but short enough to run quickly."
)
DEFAULT_UMBRA_URL = "http://100.72.151.28:8771"
DEFAULT_MAC_URL = "http://127.0.0.1:8772"


@dataclass
class BenchResult:
    name: str
    ok: bool
    engine: str
    url: str
    sample_path: str = ""
    generation_seconds: float | None = None
    audio_seconds: float | None = None
    real_time_factor: float | None = None
    chars_per_second: float | None = None
    bytes: int | None = None
    error: str = ""


def run_bench(*, output_dir: Path, text: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = [
        ("umbra-chatterbox", _env("DOC_READER_TTS_UMBRA_URL", DEFAULT_UMBRA_URL), "chatterbox"),
        ("umbra-kokoro", _env("DOC_READER_TTS_UMBRA_URL", DEFAULT_UMBRA_URL), "kokoro"),
        ("mac-kokoro", _env("DOC_READER_TTS_MAC_URL", DEFAULT_MAC_URL), "kokoro"),
    ]
    results = [_bench_http(name=name, url=url, engine=engine, output_dir=output_dir, text=text) for name, url, engine in targets]
    results.append(_bench_macsay(output_dir=output_dir, text=text))
    payload = {
        "ok": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "results": [asdict(result) for result in results],
    }
    report_path = output_dir / "benchmark.json"
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["report_path"] = str(report_path)
    return payload


def _bench_http(*, name: str, url: str, engine: str, output_dir: Path, text: str) -> BenchResult:
    speech_url = f"{url.rstrip('/')}/v1/audio/speech"
    payload = json.dumps({"engine": engine, "text": text, "format": "wav"}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    started = time.perf_counter()
    req = request.Request(speech_url, data=payload, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=180) as response:
            audio = response.read()
            elapsed = time.perf_counter() - started
            sample_path = output_dir / f"{name}.wav"
            sample_path.write_bytes(audio)
            generation_seconds = _header_float(response.headers, "X-Doc-Reader-Generation-Seconds") or elapsed
            audio_seconds = _header_float(response.headers, "X-Doc-Reader-Audio-Seconds")
            return BenchResult(
                name=name,
                ok=True,
                engine=engine,
                url=url,
                sample_path=str(sample_path),
                generation_seconds=generation_seconds,
                audio_seconds=audio_seconds,
                real_time_factor=(
                    generation_seconds / audio_seconds
                    if generation_seconds is not None and audio_seconds
                    else None
                ),
                chars_per_second=len(text) / generation_seconds if generation_seconds else None,
                bytes=len(audio),
            )
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        return BenchResult(name=name, ok=False, engine=engine, url=url, error=f"HTTP {exc.code}: {detail}")
    except Exception as exc:  # noqa: BLE001
        return BenchResult(name=name, ok=False, engine=engine, url=url, error=f"{type(exc).__name__}: {exc}")


def _bench_macsay(*, output_dir: Path, text: str) -> BenchResult:
    say_bin = shutil.which("say")
    if not say_bin:
        return BenchResult(name="macsay", ok=False, engine="macsay", url="local", error="say command not found")
    sample_path = output_dir / "macsay.aiff"
    started = time.perf_counter()
    try:
        subprocess.run(
            [say_bin, "-o", str(sample_path), text],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
        elapsed = time.perf_counter() - started
        return BenchResult(
            name="macsay",
            ok=True,
            engine="macsay",
            url="local",
            sample_path=str(sample_path),
            generation_seconds=elapsed,
            chars_per_second=len(text) / elapsed if elapsed > 0 else None,
            bytes=sample_path.stat().st_size if sample_path.exists() else None,
        )
    except subprocess.CalledProcessError as exc:
        return BenchResult(name="macsay", ok=False, engine="macsay", url="local", error=exc.stderr.strip())
    except Exception as exc:  # noqa: BLE001
        return BenchResult(name="macsay", ok=False, engine="macsay", url="local", error=f"{type(exc).__name__}: {exc}")


def _header_float(headers, name: str) -> float | None:
    value = headers.get(name)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def _default_output_dir() -> Path:
    root = os.getenv("DOC_READER_MANAGED_ROOT")
    base = Path(root).expanduser() if root else Path.home() / ".doc-reader-managed"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return base / "tts-benchmarks" / stamp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark DocReader local TTS backends.")
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--output-dir", type=Path, default=_default_output_dir())
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = run_bench(output_dir=args.output_dir.expanduser(), text=args.text)
    print(json.dumps(payload, indent=2))
    return 0 if any(result.get("ok") for result in payload["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
