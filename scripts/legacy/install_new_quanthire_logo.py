"""
Process the new QuantHire logo image into all brand assets:
1. quanthire-logo-full.png (full lockup with transparent background)
2. quanthire-logo-nav.png (compact lockup with transparent background)
3. quanthire-mark.png (512x512 circular Q-mark with transparent background)
4. favicon.ico, apple-icon.png, icon.png
"""

import os
from PIL import Image, ImageDraw

SRC_PATH = r"C:\Users\prakumar\.gemini\antigravity\brain\b6364c16-d326-4bf6-ac3e-f70ab439764c\.user_uploaded\media_1786967234996.png"
BRAND_DIR = r"d:\QuantHire AI\apps\web\public\brand"
APP_DIR = r"d:\QuantHire AI\apps\web\src\app"
PUB_DIR = r"d:\QuantHire AI\apps\web\public"

def make_circle_mask(im, size=512):
    scale = 4
    big = size * scale
    resized = im.resize((big, big), Image.Resampling.LANCZOS)
    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, big - 1, big - 1), fill=255)
    
    res = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    res.paste(resized, (0, 0), mask)
    return res.resize((size, size), Image.Resampling.LANCZOS)

def main():
    im = Image.open(SRC_PATH).convert("RGBA")
    print(f"Loaded master image: {im.size}")
    
    # 1. Full trimmed logo lockup
    # BBox of visible content
    bbox = im.getbbox()
    print(f"BBox: {bbox}")
    
    # Crop tightly around content with small 4px margin
    margin = 4
    x0 = max(0, bbox[0] - margin)
    y0 = max(0, bbox[1] - margin)
    x1 = min(im.width, bbox[2] + margin)
    y1 = min(im.height, bbox[3] + margin)
    
    full_cropped = im.crop((x0, y0, x1, y1))
    full_path = os.path.join(BRAND_DIR, "quanthire-logo-full.png")
    full_cropped.save(full_path, "PNG", optimize=True)
    print(f"Saved full logo: {full_path} -> {full_cropped.size}")
    
    # 2. Nav cropped logo (without the bottom feature row)
    # The bottom feature row starts around 82% of height
    nav_h = int(full_cropped.height * 0.82)
    nav_cropped = full_cropped.crop((0, 0, full_cropped.width, nav_h))
    nav_path = os.path.join(BRAND_DIR, "quanthire-logo-nav.png")
    nav_cropped.save(nav_path, "PNG", optimize=True)
    print(f"Saved nav logo: {nav_path} -> {nav_cropped.size}")
    
    # 3. Mark extraction (Q icon on left)
    # Q mark spans from x=0 to ~x=260 in original, or x0..x0+260
    # Let's crop the square around the Q mark
    q_crop = im.crop((0, bbox[1], 268, bbox[3]))
    # Make it a square
    side = max(q_crop.size)
    q_square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ox = (side - q_crop.width) // 2
    oy = (side - q_crop.height) // 2
    q_square.paste(q_crop, (ox, oy), q_crop)
    
    # Circle mask
    mark = make_circle_mask(q_square, 512)
    mark_path = os.path.join(BRAND_DIR, "quanthire-mark.png")
    mark.save(mark_path, "PNG", optimize=True)
    print(f"Saved circular mark: {mark_path} -> {mark.size}")
    
    # 4. Favicons
    # Apple icon (180x180)
    apple = mark.resize((180, 180), Image.Resampling.LANCZOS)
    apple.save(os.path.join(APP_DIR, "apple-icon.png"), "PNG", optimize=True)
    apple.save(os.path.join(PUB_DIR, "apple-icon.png"), "PNG", optimize=True)
    
    # Icon 32x32
    icon32 = mark.resize((32, 32), Image.Resampling.LANCZOS)
    icon32.save(os.path.join(APP_DIR, "icon.png"), "PNG", optimize=True)
    
    # Favicon.ico (16, 32, 48)
    icon16 = mark.resize((16, 16), Image.Resampling.LANCZOS)
    icon48 = mark.resize((48, 48), Image.Resampling.LANCZOS)
    for p in [os.path.join(APP_DIR, "favicon.ico"), os.path.join(PUB_DIR, "favicon.ico")]:
        icon32.save(p, "ICO", sizes=[(16, 16), (32, 32), (48, 48)], append_images=[icon16, icon48])
    
    # Favicon source
    mark1024 = make_circle_mask(q_square, 1024)
    mark1024.save(os.path.join(BRAND_DIR, "quanthire-favicon-source.png"), "PNG", optimize=True)
    print("Saved all favicons!")

if __name__ == "__main__":
    main()
