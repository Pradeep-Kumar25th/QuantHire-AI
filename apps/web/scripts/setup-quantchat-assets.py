"""
Install QuantChat AI brand assets from approved logo PNGs.

Run from apps/web:
  pip install Pillow
  python scripts/setup-quantchat-assets.py

Uses the circular QuantChat badge PNG by default for launcher/header,
and an icon-only circular crop for message avatars.
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_BRAND = WEB_ROOT / "public" / "brand"

DEFAULT_CIRCULAR_SOURCE = Path(
    r"C:\Users\prakumar\.cursor\projects\d-QuantHire-AI\assets"
    r"\c__Users_prakumar_AppData_Roaming_Cursor_User_workspaceStorage_486f2694f1bdf0b8cca5595157957c1f"
    r"_images_ChatGPT_Image_Aug_16__2026__11_26_59_PM-6e305bdf-5e0e-44b2-834e-fce60cdceed5.png"
)

DEFAULT_SHEET_SOURCE = Path(
    r"C:\Users\prakumar\.cursor\projects\d-QuantHire-AI\assets"
    r"\c__Users_prakumar_AppData_Roaming_Cursor_User_workspaceStorage_486f2694f1bdf0b8cca5595157957c1f"
    r"_images_ChatGPT_Image_Aug_16__2026__10_27_02_PM-f5c40025-e39d-4f72-94b6-7c4c96da19b6.png"
)

DEFAULT_VERTICAL_SOURCE = Path(
    r"C:\Users\prakumar\.cursor\projects\d-QuantHire-AI\assets"
    r"\c__Users_prakumar_AppData_Roaming_Cursor_User_workspaceStorage_486f2694f1bdf0b8cca5595157957c1f"
    r"_images_ChatGPT_Image_Aug_16__2026__10_27_08_PM-c3ae5384-274e-4125-958f-663cc5cabbf1.png"
)


def remove_background_flood(im, tolerance: int = 36):
    from PIL import Image

    rgba = im.convert("RGBA")
    w, h = rgba.size
    pixels = rgba.load()
    visited: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()

    def is_background(r: int, g: int, b: int) -> bool:
        return r <= tolerance and g <= tolerance and b <= tolerance

    for x in range(w):
        for y in (0, h - 1):
            r, g, b, _a = pixels[x, y]
            if is_background(r, g, b):
                queue.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            r, g, b, _a = pixels[x, y]
            if is_background(r, g, b):
                queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        if (x, y) in visited:
            continue
        r, g, b, a = pixels[x, y]
        if not is_background(r, g, b):
            continue
        visited.add((x, y))
        pixels[x, y] = (r, g, b, 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                queue.append((nx, ny))

    return rgba


def trim_transparent(im):
    rgba = im.convert("RGBA")
    bbox = rgba.getbbox()
    return rgba.crop(bbox) if bbox else rgba


def square_canvas(im, size: int = 512):
    from PIL import Image

    rgba = trim_transparent(im)
    side = max(rgba.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ox = (side - rgba.width) // 2
    oy = (side - rgba.height) // 2
    canvas.paste(rgba, (ox, oy), rgba)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def apply_circular_mask(im, inset_ratio: float = 0.01):
    from PIL import Image, ImageDraw

    rgba = im.convert("RGBA")
    side = rgba.size[0]
    mask = Image.new("L", (side, side), 0)
    draw = ImageDraw.Draw(mask)
    pad = int(side * inset_ratio)
    draw.ellipse((pad, pad, side - pad - 1, side - pad - 1), fill=255)
    rgba.putalpha(mask)
    return rgba


def crop_icon_from_badge(squared_im, top_ratio: float = 0.52):
    """Keep the Q bubble (top portion), drop the wordmark for small avatars."""
    w, h = squared_im.size
    icon_h = int(h * top_ratio)
    icon = squared_im.crop((0, 0, w, icon_h))
    trimmed = trim_transparent(icon)
    return square_canvas(trimmed, squared_im.size[0])


def crop_fraction(im, left: float, top: float, right: float, bottom: float):
    w, h = im.size
    return im.crop((int(w * left), int(h * top), int(w * right), int(h * bottom)))


def crop_icon_from_vertical(im):
    w, h = im.size
    icon_h = int(h * 0.56)
    side = min(w, icon_h)
    left = (w - side) // 2
    return im.crop((left, 0, left + side, side))


def build_from_circular(circular_path: Path, public_brand: Path) -> None:
    from PIL import Image

    master = Image.open(circular_path)
    cleaned = remove_background_flood(master, tolerance=42)
    squared = square_canvas(cleaned, 512)

    badge = apply_circular_mask(squared, inset_ratio=0.008)
    badge_path = public_brand / "quantchat-circle.png"
    badge.save(badge_path, "PNG", optimize=True)
    print(f"Wrote circular badge -> {badge_path}")

    icon_only = crop_icon_from_badge(squared, top_ratio=0.52)
    mark = apply_circular_mask(icon_only, inset_ratio=0.012)
    mark_path = public_brand / "quantchat-mark.png"
    mark.save(mark_path, "PNG", optimize=True)
    print(f"Wrote circular icon mark -> {mark_path}")


def build_nav_and_full(sheet_path: Path | None, vertical_path: Path | None, public_brand: Path) -> None:
    from PIL import Image

    full_path = public_brand / "quantchat-logo-full.png"
    nav_path = public_brand / "quantchat-logo-nav.png"

    if sheet_path and sheet_path.is_file():
        sheet = Image.open(sheet_path)
        full_region = crop_fraction(sheet, 0.03, 0.04, 0.49, 0.47)
        full = trim_transparent(remove_background_flood(full_region))
        full.save(full_path, "PNG", optimize=True)
        fw, fh = full.size
        full.crop((0, 0, fw, int(fh * 0.72))).save(nav_path, "PNG", optimize=True)
        print(f"Wrote full/nav from brand sheet")
        return

    if vertical_path and vertical_path.is_file():
        vertical = Image.open(vertical_path)
        cleaned = remove_background_flood(vertical)
        full = trim_transparent(cleaned)
        full.save(full_path, "PNG", optimize=True)
        fw, fh = full.size
        full.crop((0, 0, fw, int(fh * 0.72))).save(nav_path, "PNG", optimize=True)
        print(f"Wrote full/nav from vertical logo")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--circular-source",
        type=Path,
        default=DEFAULT_CIRCULAR_SOURCE,
        help="Circular QuantChat badge (launcher + header + avatar base)",
    )
    parser.add_argument("--sheet-source", type=Path, default=DEFAULT_SHEET_SOURCE)
    parser.add_argument("--vertical-source", type=Path, default=DEFAULT_VERTICAL_SOURCE)
    args = parser.parse_args()

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("Install Pillow: pip install Pillow")
        return 1

    PUBLIC_BRAND.mkdir(parents=True, exist_ok=True)
    circular_src: Path = args.circular_source

    if not circular_src.is_file():
        print(f"Circular source not found: {circular_src}")
        return 1

    build_from_circular(circular_src, PUBLIC_BRAND)
    build_nav_and_full(
        args.sheet_source if args.sheet_source.is_file() else None,
        args.vertical_source if args.vertical_source.is_file() else None,
        PUBLIC_BRAND,
    )

    print("\nQuantChat brand assets ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
