"""
Generate perfectly circular favicon assets from the QuantHire icon.
Creates:
  - favicon.ico  (32x32 + 16x16, circular, anti-aliased)
  - icon.png     (32x32, circular, anti-aliased)
  - apple-icon.png (180x180, circular, anti-aliased)
  - quanthire-mark.png (512x512, circular, anti-aliased) — brand mark
"""

from PIL import Image, ImageDraw
import os

SRC = r"d:\QuantHire AI\apps\web\public\brand\quanthire-mark.png"

# Output paths
APP_DIR  = r"d:\QuantHire AI\apps\web\src\app"
PUB_DIR  = r"d:\QuantHire AI\apps\web\public"
BRAND_DIR = r"d:\QuantHire AI\apps\web\public\brand"

def make_circle(img: Image.Image, size: int) -> Image.Image:
    """Resize image and apply a perfect circular mask with anti-aliased edges."""
    # Work at 4x resolution for smooth anti-aliasing
    scale = 4
    big_size = size * scale

    # Resize source to big size with high-quality resampling
    resized = img.resize((big_size, big_size), Image.LANCZOS)

    # Create circular mask at high resolution
    mask = Image.new("L", (big_size, big_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, big_size - 1, big_size - 1), fill=255)

    # Apply mask
    result = Image.new("RGBA", (big_size, big_size), (0, 0, 0, 0))
    result.paste(resized, (0, 0), mask)

    # Downscale to final size for smooth anti-aliased edges
    result = result.resize((size, size), Image.LANCZOS)

    return result


def main():
    print("Loading source icon...")
    src = Image.open(SRC).convert("RGBA")
    print(f"  Source: {src.size[0]}x{src.size[1]}, mode={src.mode}")

    # 1. Brand mark (512x512 circular)
    print("\n1. Generating quanthire-mark.png (512x512 circular)...")
    mark = make_circle(src, 512)
    mark_path = os.path.join(BRAND_DIR, "quanthire-mark.png")
    mark.save(mark_path, "PNG", optimize=True)
    print(f"   ✅ Saved: {mark_path} ({os.path.getsize(mark_path):,} bytes)")

    # 2. Apple icon (180x180 circular)
    print("\n2. Generating apple-icon.png (180x180 circular)...")
    apple = make_circle(src, 180)
    apple_path = os.path.join(APP_DIR, "apple-icon.png")
    apple.save(apple_path, "PNG", optimize=True)
    print(f"   ✅ Saved: {apple_path} ({os.path.getsize(apple_path):,} bytes)")

    # Also copy to public root
    apple_pub_path = os.path.join(PUB_DIR, "apple-icon.png")
    apple.save(apple_pub_path, "PNG", optimize=True)
    print(f"   ✅ Saved: {apple_pub_path}")

    # 3. icon.png (32x32 circular)
    print("\n3. Generating icon.png (32x32 circular)...")
    icon32 = make_circle(src, 32)
    icon_path = os.path.join(APP_DIR, "icon.png")
    icon32.save(icon_path, "PNG", optimize=True)
    print(f"   ✅ Saved: {icon_path} ({os.path.getsize(icon_path):,} bytes)")

    # 4. favicon.ico (multi-resolution: 16x16 + 32x32 + 48x48, all circular)
    print("\n4. Generating favicon.ico (16+32+48px circular)...")
    icon16 = make_circle(src, 16)
    icon48 = make_circle(src, 48)
    favicon_path = os.path.join(APP_DIR, "favicon.ico")
    icon32.save(favicon_path, "ICO", sizes=[(16, 16), (32, 32), (48, 48)],
                append_images=[icon16, icon48])
    print(f"   ✅ Saved: {favicon_path} ({os.path.getsize(favicon_path):,} bytes)")

    # Also copy to public root
    favicon_pub_path = os.path.join(PUB_DIR, "favicon.ico")
    icon32.save(favicon_pub_path, "ICO", sizes=[(16, 16), (32, 32), (48, 48)],
                append_images=[icon16, icon48])
    print(f"   ✅ Saved: {favicon_pub_path}")

    # 5. Update quanthire-favicon-source.png for reference
    print("\n5. Generating quanthire-favicon-source.png (1024x1024 circular)...")
    favicon_src = make_circle(src, 1024)
    fav_src_path = os.path.join(BRAND_DIR, "quanthire-favicon-source.png")
    favicon_src.save(fav_src_path, "PNG", optimize=True)
    print(f"   ✅ Saved: {fav_src_path} ({os.path.getsize(fav_src_path):,} bytes)")

    print("\n" + "=" * 60)
    print("✅ All favicon assets generated with perfect circular shape!")
    print("=" * 60)
    print("\nRefresh your browser (Ctrl+Shift+R) to see the new favicon.")


if __name__ == "__main__":
    main()
