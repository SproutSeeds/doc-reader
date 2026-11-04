"""Start the bundled macOS services without Node, pip, or a system Python."""
from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Doc Reader desktop services")
    parser.add_argument("command", choices=("ensure", "stop", "status"), default="ensure", nargs="?")
    args = parser.parse_args()
    os.environ.setdefault("DOC_READER_TTS_DEVICE", "cpu")
    os.environ.setdefault("DOC_READER_STT_MODEL", "base" if sys.platform == "darwin" else "small")
    os.environ.setdefault("DOC_READER_STT_COMPUTE_TYPE", "int8")
    os.environ.setdefault("DOC_READER_TTS_ENGINES", "kokoro,whisper")
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    from . import windows_app as services

    if args.command == "status":
        return services.cmd_status()
    # Serialize native startup and fallback so a slow first model load cannot
    # create duplicate sidecars. The lock lives in the writable user data folder.
    import fcntl
    with (services._root() / "desktop-start.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == "stop":
            for name in ("web", "tts"):
                print(services.stop_service(name, quiet=True))
            return 0
        for name in ("web", "tts"):
            print(services.ensure_service(name, quiet=True), flush=True)
        return 0 if services._wait_health(services.WEB_URL, timeout=40) else 1


if __name__ == "__main__":
    raise SystemExit(main())
