# -*- coding: utf-8 -*-
"""第 07 章：解析 PCK 里的 project.binary（Godot ECFG 二进制项目设置），输出键值表。
凭据类值（sentry dsn、带 @ 的 URL、长十六进制串）一律打码。
用法: python -I -X utf8 scripts/ch07_project_settings.py
输出: data/csv/ch07_project_settings.csv
"""
import csv
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "pck_text" / "project.binary"
OUT = ROOT / "data" / "csv" / "ch07_project_settings.csv"

TYPE_NAMES = {0: "nil", 1: "bool", 2: "int", 3: "float", 4: "string", 5: "Vector2", 6: "Vector2i",
              20: "Color", 21: "StringName", 22: "NodePath", 24: "Object", 27: "Dictionary", 28: "Array",
              29: "PackedByteArray", 30: "PackedInt32Array", 31: "PackedInt64Array",
              32: "PackedFloat32Array", 34: "PackedStringArray"}


class Reader:
    def __init__(self, b, pos=0):
        self.b, self.p = b, pos

    def u32(self):
        v = struct.unpack_from("<I", self.b, self.p)[0]
        self.p += 4
        return v

    def i32(self):
        v = struct.unpack_from("<i", self.b, self.p)[0]
        self.p += 4
        return v

    def raw(self, n):
        v = self.b[self.p:self.p + n]
        self.p += n
        return v

    def string(self):
        n = self.u32()
        s = self.raw(n).decode("utf-8", "replace")
        self.p += (4 - n % 4) % 4
        return s.rstrip("\x00")


def variant(r, depth=0):
    header = r.u32()
    t = header & 0xFFFF
    flag64 = bool(header & (1 << 16))
    if t == 0:
        return None
    if t == 1:
        return bool(r.u32())
    if t == 2:
        return struct.unpack("<q", r.raw(8))[0] if flag64 else r.i32()
    if t == 3:
        return struct.unpack("<d", r.raw(8))[0] if flag64 else struct.unpack("<f", r.raw(4))[0]
    if t in (4, 21, 22) and t != 22:
        return r.string()
    if t == 5:
        return tuple(struct.unpack("<ff", r.raw(8)))
    if t == 6:
        return tuple(struct.unpack("<ii", r.raw(8)))
    if t == 20:
        return tuple(round(x, 3) for x in struct.unpack("<ffff", r.raw(16)))
    if t == 27:
        n = r.u32() & 0x7FFFFFFF
        d = {}
        for _ in range(n):
            k = variant(r, depth + 1)
            v = variant(r, depth + 1)
            d[str(k)] = v
        return d
    if t == 28:
        n = r.u32() & 0x7FFFFFFF
        return [variant(r, depth + 1) for _ in range(n)]
    if t == 34:
        n = r.u32()
        return [r.string() for _ in range(n)]
    if t == 30:
        n = r.u32()
        return list(struct.unpack("<%di" % n, r.raw(4 * n)))
    raise ValueError("unsupported variant type %d" % t)


SECRET_KEY = re.compile(r"dsn|token|secret|password|api_key|apikey", re.I)


def redact(key, text):
    if SECRET_KEY.search(key):
        return "<已打码>" if text not in ("", "None") else text
    text = re.sub(r"https?://[^\s'\"]*@[^\s'\"]*", "<URL已打码>", text)
    text = re.sub(r"\b[0-9a-fA-F]{32,}\b", "<HEX已打码>", text)
    return text


def main():
    b = SRC.read_bytes()
    if b[:4] != b"ECFG":
        sys.exit("not an ECFG file")
    r = Reader(b, 4)
    count = r.u32()
    rows = []
    for _ in range(count):
        klen = r.u32()
        key = r.raw(klen).decode("utf-8", "replace")
        vlen = r.u32()
        start = r.p
        try:
            sub = Reader(b, start)
            val = variant(sub)
            text = repr(val) if not isinstance(val, str) else val
            vtype = TYPE_NAMES.get(struct.unpack_from("<I", b, start)[0] & 0xFFFF, "?")
        except Exception as e:  # noqa: BLE001
            text, vtype = "<未解码: %s>" % e, TYPE_NAMES.get(struct.unpack_from("<I", b, start)[0] & 0xFFFF, "?")
        r.p = start + vlen
        if len(text) > 400:
            text = text[:400] + "…"
        rows.append((key, vtype, redact(key, text)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["key", "type", "value"])
        w.writerows(rows)
    print("settings:", len(rows), "->", OUT)


if __name__ == "__main__":
    main()
