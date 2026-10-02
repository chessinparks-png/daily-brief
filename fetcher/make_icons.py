"""Makes the app icons (icons/*.png) with only the standard library. Run: python fetcher/make_icons.py"""
import struct, zlib, pathlib

BG = (17, 16, 14)
BARS = [(233, 162, 59), (111, 160, 255), (255, 122, 99), (63, 203, 139), (179, 147, 255), (255, 127, 179)]
WIDTHS = [1.0, 0.86, 0.72, 0.58, 0.44, 0.30]  # a stack of lines that shortens, like a brief


def png(size, safe):
    """safe=True keeps the art inside the middle 80% (for maskable icons)."""
    pad = size * (0.2 if safe else 0.16)
    area = size - 2 * pad
    bar_h = area / (len(BARS) * 2 - 1)
    rows = []
    for y in range(size):
        row = bytearray()
        i = int((y - pad) // bar_h) if y >= pad else -1
        in_bar = 0 <= i < len(BARS) * 2 - 1 and i % 2 == 0
        for x in range(size):
            c = BG
            if in_bar:
                k = i // 2
                if pad <= x < pad + area * WIDTHS[k]:
                    c = BARS[k]
            row += bytes(c)
        rows.append(b"\x00" + bytes(row))
    raw = b"".join(rows)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


out = pathlib.Path(__file__).resolve().parent.parent / "icons"
out.mkdir(exist_ok=True)
for name, size, safe in [("icon-180.png", 180, False), ("icon-192.png", 192, False),
                         ("icon-512.png", 512, False), ("icon-maskable-512.png", 512, True)]:
    (out / name).write_bytes(png(size, safe))
    print("wrote", out / name)
