# -*- coding: utf-8 -*-
"""生成手机扫码直达的二维码（QR 里存的是 address.txt 里的地址）。"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "qrlibs"))

import segno  # noqa: E402

addr = (ROOT / "address.txt")
url = addr.read_text(encoding="utf-8").strip() if addr.exists() else "http://127.0.0.1:8787"

qr = segno.make_qr(url, error="m")
qr.save(ROOT / "qr.png", scale=10, border=3, dark="#0b1220", light="#ffffff")
qr.save(ROOT / "qr.svg", scale=10, border=3, dark="#0b1220", light="#ffffff")
print("URL :", url)
print("PNG :", ROOT / "qr.png")
print("SVG :", ROOT / "qr.svg")
