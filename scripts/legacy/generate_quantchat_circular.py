"""
Generate perfectly circular QuantChat assets from the source logo.
Creates:
  - quantchat-circle.png  (512x512 circular, anti-aliased) — floating bubble + header badge
  - quantchat-mark.png    (512x512 circular, anti-aliased) — message avatars
"""

from PIL import Image, ImageDraw
import os

BRAND_DIR = r"d:\QuantHire AI\apps\web\public\brand"
SRC = os.path.join(BRAND_DIR, "quantchat-circle.png")


def make_circle(img: Image.Image, size: int) -> Image.Image:
    """Resize and apply a perfect circular mask with 4x super-sampled anti-aliasing."""
    scale = 4
    big = size * scale

    resized = img.resize((big, big), Image.LANCZOS)

    # Create perfect circular mask
    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, big - 1, big - 1), fill=255)

    # Apply mask on transparent canvas
    result = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    result.paste(resized, (0, 0), mask)

    # Downscale for smooth anti-aliased edges
    return result.resize((size, size), Image.LANCZOS)


def crop_center_square(img: Image.Image) -> Image.Image:
    """Crop the largest centered square from the image."""
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def main():
    print("Loading QuantChat source logo...")
    src = Image.open(SRC).convert("RGBA")
    print(f"  Source: {src.size[0]}x{src.size[1]}, mode={src.mode}")

    # Ensure it's square
    src = crop_center_square(src)
    print(f"  After square crop: {src.size[0]}x{src.size[1]}")

    # 1. quantchat-circle.png — Full badge with text (floating bubble + header)
    print("\n1. Generating quantchat-circle.png (512x512 circular)...")
    circle = make_circle(src, 512)
    circle_path = os.path.join(BRAND_DIR, "quantchat-circle.png")
    circle.save(circle_path, "PNG", optimize=True)
    print(f"   ✅ Saved: {circle_path} ({os.path.getsize(circle_path):,} bytes)")

    # 2. quantchat-mark.png — Same circular logo for message avatars
    #    (Using the full circle badge since the Q icon is already centered nicely)
    print("\n2. Generating quantchat-mark.png (512x512 circular)...")
    mark = make_circle(src, 512)
    mark_path = os.path.join(BRAND_DIR, "quantchat-mark.png")
    mark.save(mark_path, "PNG", optimize=True)
    print(f"   ✅ Saved: {mark_path} ({os.path.getsize(mark_path):,} bytes)")

    # Verify dimensions
    print("\n📊 Verification:")
    for name in ["quantchat-circle.png", "quantchat-mark.png"]:
        p = os.path.join(BRAND_DIR, name)
        img = Image.open(p)
        print(f"   {name}: {img.size[0]}x{img.size[1]}, mode={img.mode}, "
              f"size={os.path.getsize(p):,} bytes")

    print("\n" + "=" * 60)
    print("✅ All QuantChat assets generated with perfect circular shape!")
    print("=" * 60)


if __name__ == "__main__":
    main()
