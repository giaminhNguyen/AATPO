"""Draws the AATPO icon with Qt and writes packaging/aatpo.ico (PNG-compressed ICO, valid on Windows Vista+).
Run once: .venv\\Scripts\\python packaging\\make_icon.py"""
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter

app = QGuiApplication(sys.argv)
sizes = [16, 32, 48, 64, 128, 256]
blobs = []
for s in sizes:
    img = QImage(s, s, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#1f6f5c"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, s, s, s * 0.22, s * 0.22)
    p.setPen(QColor("white"))
    f = QFont("Segoe UI", max(6, int(s * 0.5)))
    f.setBold(True)
    p.setFont(f)
    p.drawText(img.rect(), Qt.AlignCenter, "A")
    p.end()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    blobs.append(bytes(ba))
head = struct.pack("<HHH", 0, 1, len(sizes))
offset = 6 + 16 * len(sizes)
entries, data = b"", b""
for s, b in zip(sizes, blobs):
    entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(b), offset + len(data))
    data += b
out = Path(__file__).with_name("aatpo.ico")
out.write_bytes(head + entries + data)
print("wrote", out, out.stat().st_size, "bytes")
