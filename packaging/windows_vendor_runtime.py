"""Retain upstream signatures stripped by the pinned uv Python distribution.

The matching unstripped archive preserves Microsoft and Python vendor DLLs.
Never clear malformed certificate data or re-sign modified vendor binaries.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
from urllib.request import urlopen

URL = "https://github.com/astral-sh/python-build-standalone/releases/download/20250918/cpython-3.11.13%2B20250918-x86_64-pc-windows-msvc-install_only.tar.gz"
SHA256 = "c8130868bceb3525f4bdfc595646a7752c106a935e825ea4f0e4332dfb2e08fa"
FILES = ("vcruntime140.dll", "vcruntime140_1.dll", "DLLs/tcl86t.dll", "DLLs/tk86t.dll")


def restore_vendor_libraries(runtime: Path, cache: Path) -> None:
    archive = cache / "cpython-3.11.13-unstripped-windows.tar.gz"
    cache.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        with urlopen(URL, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise RuntimeError("Upstream runtime checksum mismatch")
        archive.write_bytes(data)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError("Cached upstream runtime checksum mismatch")
    with tarfile.open(archive) as source:
        for name in FILES:
            member = source.getmember("python/" + name)
            assert member.isfile(), "Vendor library must be a regular file"
            with source.extractfile(member) as stream:
                (runtime / name).write_bytes(stream.read())
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    script = "$ErrorActionPreference='Stop'; $files=[Console]::In.ReadToEnd() | ConvertFrom-Json; foreach($file in $files) { $s=Get-AuthenticodeSignature -LiteralPath $file; if($s.Status -ne 'Valid') {throw ('Vendor signature invalid: '+$file)}; Write-Output ('Verified vendor: '+$s.SignerCertificate.GetNameInfo('SimpleName',$false)+' / '+[IO.Path]::GetFileName($file)) }"
    subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
                   input=json.dumps([str(runtime / name) for name in FILES]), text=True, check=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime", type=Path)
    parser.add_argument("cache", type=Path)
    args = parser.parse_args()
    restore_vendor_libraries(args.runtime, args.cache)
