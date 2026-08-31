"""
Clean and install transparent logo from media_1786968936313.png
"""

import os
from PIL import Image, ImageDraw
import numpy as np

SRC = r"C:\Users\prakumar\.gemini\antigravity\brain\b6364c16-d326-4bf6-ac3e-f70ab439764c\.user_uploaded\media_1786968936313.png"
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
    im = Image.open(SRC).convert("RGBA")
    print(f"Loaded source image: {im.size}")
    
    # 1. Full logo: crop transparent bounding box
    bbox = im.getbbox()
    print(f"BBox: {bbox}")
    full = im.crop((bbox[0], bbox[1], bbox[2], bbox[3]))
    
    full_path = os.path.join(BRAND_DIR, "quanthire-logo-full.png")
    full.save(full_path, "PNG", optimize=True)
    print(f"Saved transparent full logo: {full_path} -> {full.size}")
    
    # 2. Nav logo: crop top 80% to exclude bottom feature dots
    nav_h = int(full.height * 0.80)
    nav = full.crop((0, 0, full.width, nav_h))
    nav_bbox = nav.getbbox()
    nav_trimmed = nav.crop(nav_bbox)
    nav_path = os.path.join(BRAND_DIR, "quanthire-logo-nav.png")
    nav_trimmed.save(nav_path, "PNG", optimize=True)
    print(f"Saved transparent nav logo: {nav_path} -> {nav_trimmed.size}")
    
    # 3. Circular Mark: extract Q icon on left
    # Q icon in trimmed image is from x=0 to ~270
    q_width = int(full.height * 1.1)
    q_crop = full.crop((0, 0, min(q_width, full.width), full.height))
    q_bbox = q_crop.getbbox()
    q_trimmed = q_crop.crop(q_bbox)
    
    # Place on transparent square canvas
    side = max(q_trimmed.size) + 8
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ox = (side - q_trimmed.width) // 2
    oy = (side - q_trimmed.height) // 2
    canvas.paste(q_trimmed, (ox, oy), q_trimmed)
    
    mark = make_circle_mask(canvas, 512)
    mark_path = os.path.join(BRAND_DIR, "quanthire-mark.png")
    mark.save(mark_path, "PNG", optimize=True)
    print(f"Saved circular transparent mark: {mark_path} -> {mark.size}")
    
    # 4. Favicons
    apple = mark.resize((180, 180), Image.Resampling.LANCZOS)
    apple.save(os.path.join(APP_DIR, "apple-icon.png"), "PNG", optimize=True)
    apple.save(os.path.join(PUB_DIR, "apple-icon.png"), "PNG", optimize=True)
    
    icon32 = mark.resize((32, 32), Image.Resampling.LANCZOS)
    icon32.save(os.path.join(APP_DIR, "icon.png"), "PNG", optimize=True)
    
    icon16 = mark.resize((16, 16), Image.Resampling.LANCZOS)
    icon48 = mark.resize((48, 48), Image.Resampling.LANCZOS)
    for p in [os.path.join(APP_DIR, "favicon.ico"), os.path.join(PUB_DIR, "favicon.ico")]:
        icon32.save(p, "ICO", sizes=[(16, 16), (32, 32), (48, 48)], append_images=[icon16, icon48])
        
    print("All transparent assets generated successfully!")

if __name__ == "__main__":
    main()
