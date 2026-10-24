"""Make the OpenFramely boot screens: the bootloader logo (BMP) and a one-frame boot animation.

Both use the kiosk's own background, accent and font, so the boot logo, the boot animation and
the kiosk follow on from each other without a flash. Writes to kiosk/.shots/boot/ (gitignored):

    logo.bmp            1920x1080, 24-bit, top-down: replaces logo.bmp in the boot partition's
                        resource block (the screen shown before Android starts)
    bootanimation.zip   stored (uncompressed) zip, a 1 s loop: the calendar square pulses and three
                        dots fade in turn under the wordmark. Replaces /system/media/bootanimation.zip
    preview.png         the bootloader logo, for checking by eye
    preview-anim.png    contact sheet of the animation frames

Run: uv run --no-project --python 3.12 --with pillow --with fonttools --with brotli python tools/boot_logo.py
"""

from __future__ import annotations

import io
import math
import pathlib
import zipfile

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "kiosk" / ".shots" / "boot"
FONTS = ROOT / "kiosk" / "web" / "fonts"
W, H = 1920, 1080
BG = (0x0F, 0x11, 0x15)  # --bg in kiosk/web/style.css
TEXT = (0xF4, 0xF6, 0xFA)  # --text
ACCENT = (0xFF, 0x8A, 0x3D)  # --accent
MUTED = (0x9A, 0xA3, 0xB2)  # --muted
FPS, FRAMES = 30, 30  # 1 s loop


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """Colour a faded toward b by t (0 = a, 1 = b)."""
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    """Inter from the kiosk's own woff2 files (decompressed in memory, no system font needed)."""
    tt = TTFont(str(FONTS / f"inter-{weight}.woff2"))
    tt.flavor = None
    buf = io.BytesIO()
    tt.save(buf)
    buf.seek(0)
    return ImageFont.truetype(buf, size)


def mark(d: ImageDraw.ImageDraw, x: int, y: int, s: int, accent: tuple[int, int, int] = ACCENT) -> None:
    """A small calendar mark: rounded square outline, a header bar and one highlighted day."""
    r, t = s // 5, max(4, s // 12)
    d.rounded_rectangle((x, y, x + s, y + s), radius=r, outline=TEXT, width=t)
    d.rectangle((x + t, y + s // 4, x + s - t, y + s // 4 + t // 2), fill=TEXT)
    c = s // 5
    d.rounded_rectangle((x + s - 2 * c - t, y + s - 2 * c - t // 2, x + s - c - t, y + s - c - t // 2), radius=c // 4, fill=accent)


def screen(pulse: float | None = None, dots: list[float] | None = None) -> Image.Image:
    """pulse: 0..1 brightness of the calendar square (None = full). dots: 0..1 brightness of each
    loading dot (None = no dots, as on the bootloader logo)."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    name = font("semibold", 84)
    s = 96  # mark size
    gap = 36
    tw = d.textlength("OpenFramely", font=name)
    x0 = int((W - (s + gap + tw)) / 2)
    yc = H // 2
    mark(d, x0, yc - s // 2, s, ACCENT if pulse is None else mix(BG, ACCENT, 0.35 + 0.65 * pulse))
    # baseline-centre the wordmark on the mark
    _, t, _, b = d.textbbox((0, 0), "OpenFramely", font=name)
    d.text((x0 + s + gap, yc - (t + b) / 2), "Open", font=name, fill=ACCENT)
    d.text((x0 + s + gap + d.textlength("Open", font=name), yc - (t + b) / 2), "Framely", font=name, fill=TEXT)
    if dots is not None:  # three dots centred under the whole logo, like the stock loader
        r, gap_d = 7, 30
        cx, cy = W // 2, yc + 110
        for i, v in enumerate(dots):
            x = cx + (i - 1) * gap_d
            d.ellipse((x - r, cy - r, x + r, cy + r), fill=mix(BG, MUTED, 0.25 + 0.75 * v))
    return img


def frame(i: int) -> Image.Image:
    """Frame i of the loop: the square breathes once per loop, the dots light up left to right."""
    t = i / FRAMES
    pulse = 0.5 - 0.5 * math.cos(2 * math.pi * t)
    dots = [(0.5 + 0.5 * math.cos(2 * math.pi * (t - k / 3))) ** 2 for k in range(3)]  # a wave, one always lit
    return screen(pulse, dots)


def write_bmp(img: Image.Image, path: pathlib.Path) -> None:
    """24-bit BMP with a negative height (top-down), the layout the stock logo.bmp uses."""
    rgb = img.convert("RGB")
    row = W * 3
    pad = (4 - row % 4) % 4
    data = bytearray()
    px = rgb.tobytes()
    for y in range(H):
        line = px[y * row : (y + 1) * row]
        # BMP pixels are BGR
        bgr = bytearray(line)
        bgr[0::3], bgr[2::3] = line[2::3], line[0::3]
        data += bgr + b"\0" * pad
    hdr = b"BM" + (54 + len(data)).to_bytes(4, "little") + b"\0\0\0\0" + (54).to_bytes(4, "little")
    dib = (40).to_bytes(4, "little") + W.to_bytes(4, "little") + (-H).to_bytes(4, "little", signed=True)
    dib += (1).to_bytes(2, "little") + (24).to_bytes(2, "little") + b"\0" * 4 + len(data).to_bytes(4, "little")
    dib += (2835).to_bytes(4, "little") * 2 + b"\0" * 8
    path.write_bytes(hdr + dib + bytes(data))


def write_anim(frames: list[Image.Image], path: pathlib.Path) -> None:
    """Android boot animation: desc.txt + part0/NN.png, stored (Android requires no compression).
    "p 0 0 part0" loops part0 until Android finishes booting, then the kiosk takes over."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        z.writestr("desc.txt", f"{W} {H} {FPS}\np 0 0 part0\n")
        for i, img in enumerate(frames):
            png = io.BytesIO()
            img.save(png, "PNG", optimize=True)
            z.writestr(f"part0/{i:02d}.png", png.getvalue())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    img = screen()
    write_bmp(img, OUT / "logo-openframely.bmp")
    frames = [frame(i) for i in range(FRAMES)]
    write_anim(frames, OUT / "bootanimation-openframely.zip")
    img.save(OUT / "preview.png")
    sheet = Image.new("RGB", (6 * 320, 5 * 180), BG)
    for i, f in enumerate(frames):
        sheet.paste(f.resize((320, 180)), ((i % 6) * 320, (i // 6) * 180))
    sheet.save(OUT / "preview-anim.png")
    for f in ("logo-openframely.bmp", "bootanimation-openframely.zip"):
        print(f, (OUT / f).stat().st_size, "bytes")


if __name__ == "__main__":
    main()
