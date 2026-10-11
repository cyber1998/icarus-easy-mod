"""Generate the app icon (amber ringed planet) as icon.png and icon.ico.

Run once after cloning or when changing the design:
    python packaging/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

SIZE = 1024
GOLD_SOFT = (255, 212, 121)
GOLD_DEEP = (224, 138, 30)
GOLD_RING = (242, 181, 68)


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def build_icon() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    center = SIZE / 2

    ring = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(ring)
    rx, ry = SIZE * 0.46, SIZE * 0.165
    ring_draw.ellipse(
        [center - rx, center - ry, center + rx, center + ry],
        outline=GOLD_RING + (255,),
        width=int(SIZE * 0.055),
    )
    ring = ring.rotate(-18, resample=Image.BICUBIC, center=(center, center))
    image.alpha_composite(ring)

    sphere = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sphere_draw = ImageDraw.Draw(sphere)
    radius = SIZE * 0.295
    steps = 200
    for step in range(steps, 0, -1):
        t = step / steps
        color = (
            _lerp(GOLD_DEEP[0], GOLD_SOFT[0], 1 - t),
            _lerp(GOLD_DEEP[1], GOLD_SOFT[1], 1 - t),
            _lerp(GOLD_DEEP[2], GOLD_SOFT[2], 1 - t),
            255,
        )
        r = radius * t
        sphere_draw.ellipse([center - r, center - r, center + r, center + r], fill=color)
    image.alpha_composite(sphere)

    mask = Image.new("L", (SIZE, SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rectangle([0, center + SIZE * 0.015, SIZE, SIZE], fill=255)
    front = ring.copy()
    front.putalpha(ImageChops.multiply(ring.getchannel("A"), mask))
    image.alpha_composite(front)

    return image.resize((512, 512), Image.LANCZOS)


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    icon = build_icon()
    png_path = out_dir / "icon.png"
    ico_path = out_dir / "icon.ico"
    icon.save(png_path)
    icon.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"wrote {png_path}")
    print(f"wrote {ico_path}")


if __name__ == "__main__":
    main()
