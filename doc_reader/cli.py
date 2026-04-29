from __future__ import annotations

import argparse
import signal
from pathlib import Path

from .config import ReaderConfig
from .pipeline import StreamingReader
from .speech import ConsoleSpeaker, build_speaker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="read-docs",
        description=(
            "Stream document narration with smart chunking so playback can start early "
            "while later sections load in the background."
        ),
    )
    parser.add_argument("source", type=Path, help="Path to .pdf, .docx, .txt, or .md file")
    parser.add_argument(
        "--mode",
        choices=("smart", "full"),
        default="smart",
        help="smart = speak key ideas, full = speak cleaned source text",
    )
    parser.add_argument(
        "--style",
        choices=("concise", "balanced", "detailed"),
        default="balanced",
        help="Controls how much detail smart mode includes",
    )
    parser.add_argument("--rate", type=int, default=180, help="Speech rate in words per minute")
    parser.add_argument(
        "--voice",
        default=None,
        help="Optional voice substring to select a specific local TTS voice",
    )
    parser.add_argument(
        "--speech-backend",
        choices=("auto", "macsay", "pyttsx3", "elevenlabs"),
        default="auto",
        help=(
            "Speech backend: auto (default), macsay, pyttsx3, or elevenlabs. "
            "Auto uses ElevenLabs when ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are set."
        ),
    )
    parser.add_argument(
        "--elevenlabs-api-key",
        default=None,
        help="Optional ElevenLabs API key (or set ELEVENLABS_API_KEY env var)",
    )
    parser.add_argument(
        "--elevenlabs-voice-id",
        default=None,
        help="Optional ElevenLabs voice id (or set ELEVENLABS_VOICE_ID env var)",
    )
    parser.add_argument(
        "--elevenlabs-model-id",
        default="eleven_multilingual_v2",
        help="ElevenLabs model id (default: eleven_multilingual_v2)",
    )
    parser.add_argument(
        "--elevenlabs-output-format",
        default="mp3_44100_128",
        help="ElevenLabs output format (default: mp3_44100_128)",
    )
    parser.add_argument(
        "--first-chunk-words",
        type=int,
        default=110,
        help="Word budget for the first chunk so narration starts quickly",
    )
    parser.add_argument(
        "--chunk-words",
        type=int,
        default=220,
        help="Word budget for subsequent chunks",
    )
    parser.add_argument(
        "--queue-size",
        type=int,
        default=8,
        help="Prefetch buffer size for prepared chunks",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Optional limit for debugging",
    )
    parser.add_argument(
        "--start-chunk-index",
        type=int,
        default=0,
        help="Start at a specific prepared chunk index (exact resume)",
    )
    parser.add_argument(
        "--start-seconds",
        type=float,
        default=0.0,
        help="Approximate playback start offset in seconds (used for rewind resume)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print prepared narration instead of speaking",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print startup and compression stats",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    source_path = args.source.expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        parser.error(f"File not found: {source_path}")

    config = ReaderConfig(
        source_path=source_path,
        mode=args.mode,
        style=args.style,
        speech_rate=args.rate,
        voice_hint=args.voice,
        queue_size=args.queue_size,
        first_chunk_words=args.first_chunk_words,
        chunk_words=args.chunk_words,
        max_chunks=args.max_chunks,
        start_chunk_index=max(0, int(args.start_chunk_index)),
        start_seconds=max(0.0, float(args.start_seconds)),
        verbose=args.verbose,
    )

    if args.dry_run:
        speaker = ConsoleSpeaker()
    else:
        try:
            speaker = build_speaker(
                rate=config.speech_rate,
                voice_hint=config.voice_hint,
                backend=args.speech_backend,
                elevenlabs_api_key=args.elevenlabs_api_key,
                elevenlabs_voice_id=args.elevenlabs_voice_id,
                elevenlabs_model_id=args.elevenlabs_model_id,
                elevenlabs_output_format=args.elevenlabs_output_format,
            )
        except RuntimeError as exc:
            print(f"[doc-reader] {exc}")
            print("[doc-reader] Falling back to dry-run mode.")
            speaker = ConsoleSpeaker()

    reader = StreamingReader(config)
    interrupted = False

    def _handle_stop_signal(_signum, _frame) -> None:
        raise KeyboardInterrupt

    # Make SIGTERM/SIGINT cooperative so active speech can be interrupted cleanly.
    signal.signal(signal.SIGTERM, _handle_stop_signal)
    signal.signal(signal.SIGINT, _handle_stop_signal)

    try:
        stats = reader.run(speaker)
    except KeyboardInterrupt:
        interrupted = True
        speaker.close()
        stats = None

    if config.verbose and stats is not None:
        print(
            "[doc-reader] startup latency: "
            f"{stats.startup_latency_seconds:.2f}s | chunks: {stats.chunks_spoken} | "
            f"source words: {stats.source_words} | spoken words: {stats.spoken_words}"
        )
        if stats.source_words:
            ratio = stats.spoken_words / stats.source_words
            print(f"[doc-reader] spoken/source ratio: {ratio:.2f}")

    if interrupted:
        print("[doc-reader] Stopped.")
        return 130

    return 0
