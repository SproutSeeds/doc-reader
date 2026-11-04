"""Pack the approved PNG sizes into Windows' multi-resolution ICO container."""
from pathlib import Path
import struct

root = Path(__file__).resolve().parents[1]
sizes = (16, 32, 48, 64, 128, 256)
images = [(root / f"doc_reader/icons/read-docs-{size}.png").read_bytes() for size in sizes]
offset = 6 + len(sizes) * 16
entries = []
for size, image in zip(sizes, images):
    entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(image), offset))
    offset += len(image)
(root / "assets/doc-reader.ico").write_bytes(struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(entries + images))
