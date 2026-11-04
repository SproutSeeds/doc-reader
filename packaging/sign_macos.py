"""Sign every embedded Mach-O, then create a release DMG. Notarize separately."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MAGIC = {b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'}


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


parser = argparse.ArgumentParser()
parser.add_argument('app', type=Path)
parser.add_argument('--identity', required=True)
parser.add_argument('--target', choices=['Apple-Silicon', 'Intel'], required=True)
parser.add_argument('--output', type=Path, default=ROOT / 'dist')
args = parser.parse_args()
app = args.app.resolve()
version = json.loads((ROOT / 'package.json').read_text())['version']
args.output.mkdir(parents=True, exist_ok=True)
entitlements = ROOT / 'packaging/python-entitlements.plist'
for path in sorted(app.rglob('*'), key=lambda p: len(p.parts), reverse=True):
    if path.is_symlink() or not path.is_file():
        continue
    with path.open('rb') as stream:
        macho = stream.read(4) in MAGIC
    if macho:
        run('codesign', '--force', '--timestamp', '--options', 'runtime', '--entitlements', entitlements, '--sign', args.identity, path)
run('codesign', '--force', '--timestamp', '--options', 'runtime', '--sign', args.identity, app)
run('codesign', '--verify', '--deep', '--strict', app)
image_root = args.output / f'dmg-{args.target}'
image_root.mkdir(exist_ok=True)
staged_app = image_root / app.name
if staged_app.exists():
    raise RuntimeError(f'Refusing to overwrite a staged app: {staged_app}')
run('ditto', app, staged_app)
(image_root / 'Applications').symlink_to('/Applications')
dmg = args.output / f'Doc-Reader-{version}-macOS-{args.target}.dmg'
run('hdiutil', 'create', '-volname', 'Doc Reader', '-srcfolder', image_root, '-ov', '-format', 'UDZO', dmg)
run('codesign', '--force', '--timestamp', '--sign', args.identity, dmg)
print(dmg)
