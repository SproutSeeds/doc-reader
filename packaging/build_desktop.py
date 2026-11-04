"""Build a relocatable desktop payload. Run on the target OS/architecture.

uv is a build-time tool only. No installer runs pip, uv, npm, or a compiler.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args: object, **kwargs: object) -> None:
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    windows = sys.platform == "win32"
    if not windows:
        run("bash", ROOT / "build-macos-app", output)
        payload = output / "Doc Reader.app" / "Contents" / "Resources"
    else:
        payload = output / "Doc Reader"
        payload.mkdir(exist_ok=True)
    runtime = payload / "runtime"
    if not runtime.exists():
        install = output / "python-build"
        run("uv", "python", "install", "3.11.13", "--install-dir", install, "--no-bin", "--no-registry")
        installed = next(install.glob("cpython-*"))
        shutil.copytree(installed, runtime, symlinks=True)
    python = runtime / ("python.exe" if windows else "bin/python3")
    run("uv", "pip", "install", "--python", python, "--system", "--break-system-packages",
        "-r", ROOT / "packaging/requirements-desktop.txt")
    site = Path(subprocess.check_output([str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"], text=True).strip())
    if sys.platform == "darwin" and platform.machine() == "x86_64":
        # Torch 2.2 and CTranslate2 ship separate Intel OpenMP runtimes. Loading
        # both aborts during real inference. Link CTranslate2 to Torch's already
        # loaded runtime instead of disabling OpenMP's duplicate-runtime guard.
        library = site / "ctranslate2/.dylibs/libctranslate2.4.6.0.dylib"
        run("install_name_tool", "-change", "@loader_path/libiomp5.dylib",
            "@loader_path/../../functorch/.dylibs/libiomp5.dylib", library)
        run("codesign", "--force", "--sign", "-", library)
    for name in ("doc_reader", "assets"):
        shutil.copytree(ROOT / name, site / name, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(ROOT / "package.json", site / "package.json")
    shutil.copy2(ROOT / "LICENSE", payload / "LICENSE.txt")
    shutil.copy2(ROOT / "packaging/THIRD_PARTY.md", payload / "THIRD_PARTY.txt")
    shutil.copytree(ROOT / "packaging/licenses", payload / "licenses", dirs_exist_ok=True)
    versions = subprocess.check_output([str(python), "-c", "import importlib.metadata as m,json; print(json.dumps(sorted([(d.metadata['Name'],d.version) for d in m.distributions()])))"], text=True)
    (payload / "runtime-packages.json").write_text(versions, encoding="utf-8")
    # Installed console scripts contain build-machine shebangs. They are unused;
    # package execution always uses the bundled interpreter with -m.
    if not windows:
        for path in (runtime / "bin").iterdir():
            if path.is_file() and not path.is_symlink() and path.read_bytes()[:2] == b"#!":
                path.unlink()
        for path in (runtime / "bin").iterdir():
            if path.is_symlink() and not path.exists():
                path.unlink()
    if windows:
        compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        run(compiler, "/nologo", "/target:winexe", f"/out:{payload / 'DocReader.exe'}",
            f"/win32icon:{ROOT / 'assets/doc-reader.ico'}", "/reference:System.Windows.Forms.dll",
            ROOT / "packaging/WindowsLauncher.cs")
    run(python, ROOT / "packaging/smoke_desktop.py")
    print(f"Desktop payload: {payload}", flush=True)


if __name__ == "__main__":
    main()
