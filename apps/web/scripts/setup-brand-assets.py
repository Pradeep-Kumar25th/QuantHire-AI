"""
Install QuantHire AI brand assets from the official logo PNG.

Run from apps/web:
  pip install Pillow
  python scripts/setup-brand-assets.py

Default source: public/brand/quanthire-logo-source.png (official lockup)

Optional:
  python scripts/setup-brand-assets.py --source "path/to/logo.png"
  python scripts/setup-brand-assets.py --favicon-source "path/to/square-q.png"
"""

from __future__ import annotations

import argparse
import io
import shutil
from collections import deque
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_BRAND = WEB_ROOT / "public" / "brand"
APP_DIR = WEB_ROOT / "src" / "app"

SOURCE_CANDIDATES = (
    PUBLIC_BRAND / "quanthire-logo-source.png",
    Path(
        r"C:\Users\prakumar\.cursor\projects\d-QuantHire-AI\assets"
        r"\quanthire-logo-source.png"
    ),
    Path(
        r"C:\Users\prakumar\.cursor\projects\d-QuantHire-AI\assets"
        r"\c__Users_prakumar_AppData_Roaming_Cursor_User_workspaceStorage_486f2694f1bdf0b8cca5595157957c1f"
        r"_images_ChatGPT_Image_Aug_17__2026__05_04_01_PM__1_-cf538ae5-33eb-4618-9ec3-4f63e9736b12.png"
    ),
)


def resolve_logo_source(explicit: Path | None) -> Path | None:
    if explicit and explicit.is_file():
        return explicit
    for candidate in SOURCE_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def remove_background_flood(im, tolerance: int = 36):
    """Flood-fill near-black pixels connected to image edges (transparent background)."""
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
        if x > 0:
            queue.append((x - 1, y))
        if x < w - 1:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y < h - 1:
            queue.append((x, y + 1))

    return rgba


def crop_mark_from_full(im):
    """Extract the circular Q mark from the left of the official horizontal lockup."""
    from PIL import Image

    rgba = im.convert("RGBA")
    w, h = rgba.size
    crop_w = int(w * 0.34)
    crop_h = int(h * 0.58)
    left = int(w * 0.01)
    top = int(h * 0.06)
    mark = rgba.crop((left, top, left + crop_w, top + crop_h))
    return mark.resize((512, 512), Image.Resampling.LANCZOS)


def apply_circular_mask(im, inset_ratio: float = 0.02):
    from PIL import Image, ImageDraw

    rgba = im.convert("RGBA")
    size = rgba.size[0]
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    pad = int(size * inset_ratio)
    draw.ellipse((pad, pad, size - pad - 1, size - pad - 1), fill=255)
    rgba.putalpha(mask)
    return rgba


def round_mark(im, size: int = 512):
    from PIL import Image

    rgba = im.convert("RGBA")
    side = min(rgba.size)
    left = (rgba.width - side) // 2
    top = (rgba.height - side) // 2
    squared = rgba.crop((left, top, left + side, top + side)).resize(
        (size, size),
        Image.Resampling.LANCZOS,
    )
    return apply_circular_mask(squared, inset_ratio=0.008)


def write_favicon_assets(mark, web_root: Path, app_dir: Path) -> None:
    from PIL import Image

    icon32 = mark.resize((32, 32), Image.Resampling.LANCZOS)
    apple = mark.resize((180, 180), Image.Resampling.LANCZOS)

    apple.save(web_root / "public" / "apple-icon.png", "PNG", optimize=True)
    apple.save(app_dir / "apple-icon.png", "PNG", optimize=True)
    icon32.save(app_dir / "icon.png", "PNG", optimize=True)

    for ico_path in (web_root / "public" / "favicon.ico", app_dir / "favicon.ico"):
        ico_path.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.BytesIO()
        icon32.save(
            buffer,
            format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48)],
        )
        ico_path.write_bytes(buffer.getvalue())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=SOURCE_CANDIDATES[0],
        help="Official horizontal logo lockup (source of truth)",
    )
    parser.add_argument(
        "--favicon-source",
        type=Path,
        default=None,
        help="Optional square Q icon; defaults to crop from --source",
    )
    args = parser.parse_args()

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("Install Pillow: pip install Pillow")
        return 1

    PUBLIC_BRAND.mkdir(parents=True, exist_ok=True)
    APP_DIR.mkdir(parents=True, exist_ok=True)

    explicit = args.source if args.source.is_file() else None
    full_src = resolve_logo_source(explicit) or resolve_logo_source(None)
    if not full_src:
        print("Logo source not found.")
        print("Place the official PNG at public/brand/quanthire-logo-source.png")
        return 1

    dest_source = PUBLIC_BRAND / "quanthire-logo-source.png"
    if full_src.resolve() != dest_source.resolve():
        shutil.copy2(full_src, dest_source)
        print(f"Copied source -> {dest_source}")

    full_master = Image.open(full_src)
    full = remove_background_flood(full_master)
    bbox = full.getbbox()
    full_trimmed = full.crop(bbox) if bbox else full
    tfw, tfh = full_trimmed.size

    full_path = PUBLIC_BRAND / "quanthire-logo-full.png"
    full_trimmed.save(full_path, "PNG", optimize=True)
    print(f"Wrote full logo (with Multi-Agent / Explainable / Evidence-Backed) -> {full_path}")

    nav_h = max(1, int(tfh * 0.68))
    nav_crop = full_trimmed.crop((0, 0, tfw, nav_h))
    nav_path = PUBLIC_BRAND / "quanthire-logo-nav.png"
    nav_crop.save(nav_path, "PNG", optimize=True)
    print(f"Wrote nav logo (wordmark + tagline) -> {nav_path}")

    favicon_src = args.favicon_source
    if favicon_src and favicon_src.is_file():
        favicon_master = Image.open(favicon_src)
        cleaned = remove_background_flood(favicon_master)
        mark = round_mark(cleaned, 512)
        shutil.copy2(favicon_src, PUBLIC_BRAND / "quanthire-favicon-source.png")
    else:
        mark = round_mark(remove_background_flood(crop_mark_from_full(full_master)), 512)

    mark_path = PUBLIC_BRAND / "quanthire-mark.png"
    mark.save(mark_path, "PNG", optimize=True)
    write_favicon_assets(mark, WEB_ROOT, APP_DIR)
    print(f"Wrote mark + favicon (circular Q) -> {mark_path}")
    print("Wrote favicon.ico, apple-icon.png, src/app/icon.png, src/app/favicon.ico")
    print("\nBrand assets ready. Commit public/brand/* and favicon files before deploy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
