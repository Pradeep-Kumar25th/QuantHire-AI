"""
Accurate color segmentation for dark-theme transparent logo.
- Q-mark (x < 265) -> keep 100% untouched
- Quant (dark slate/black) -> bright metallic white (#FFFFFF)
- Hire (teal) -> vibrant sky cyan (#38BDF8)
- AI (red to cyan gradient) -> keep 100% untouched
- Dot on 'i' in Hire (amber/yellow) -> keep 100% untouched
- Tagline & feature text (dark slate) -> bright white (#E2E8F0)
- Colored dots (red, amber, cyan) -> keep 100% untouched
"""

import os
from PIL import Image
import numpy as np

BRAND_DIR = r"d:\QuantHire AI\apps\web\public\brand"
SRC = r"C:\Users\prakumar\.gemini\antigravity\brain\b6364c16-d326-4bf6-ac3e-f70ab439764c\.user_uploaded\media_1786968936313.png"

def make_dark_variant(im_rgba):
    arr = np.array(im_rgba, dtype=np.float32)
    h, w, _ = arr.shape
    
    # Q-mark boundary
    q_mark_x = 265
    
    for y in range(h):
        for x in range(q_mark_x, w):
            a = arr[y, x, 3]
            if a < 10:
                continue
            
            r, g, b = arr[y, x, 0], arr[y, x, 1], arr[y, x, 2]
            
            # Check if this pixel is part of 'AI' (strong red or strong purple/cyan gradient)
            is_ai_letter = (x > w * 0.78 and y < h * 0.65)
            # Check if it's the amber dot on 'i' in Hire
            is_amber_dot = (r > 180 and g > 140 and b < 50 and y < h * 0.45)
            # Check if it's the bottom colored dots
            is_bottom_colored_dot = (y > h * 0.70 and (
                (r > 160 and g < 50 and b < 50) or  # red dot
                (r > 160 and g > 130 and b < 50) or # amber dot
                (r < 50 and g > 120 and b > 180)    # cyan dot
            ))
            # Check if it's the gradient horizontal lines
            is_gradient_line = (y > h * 0.60 and y < h * 0.72 and (r > 150 or b > 150))
            
            if is_ai_letter or is_amber_dot or is_bottom_colored_dot or is_gradient_line:
                continue
            
            # Check if it's 'Hire' teal
            is_hire_teal = (g > 70 and b > 90 and b > r + 20 and y < h * 0.65)
            
            if is_hire_teal:
                # Map teal to vibrant cyan (#38BDF8 / #00D2FF)
                arr[y, x, 0] = min(255.0, r * 1.6 + 50.0)
                arr[y, x, 1] = min(255.0, g * 1.4 + 75.0)
                arr[y, x, 2] = min(255.0, b * 1.3 + 90.0)
            else:
                # It's 'Quant' or subtitle text (dark slate / black)
                # Map to crisp metallic white
                brightness = max(r, g, b) / 255.0
                val = 240 + int(15 * brightness)
                arr[y, x, 0] = val
                arr[y, x, 1] = val
                arr[y, x, 2] = val

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

def main():
    im = Image.open(SRC).convert("RGBA")
    bbox = im.getbbox()
    full_light = im.crop((bbox[0], bbox[1], bbox[2], bbox[3]))
    
    # Save light versions
    full_light.save(os.path.join(BRAND_DIR, "quanthire-logo-full.png"), "PNG", optimize=True)
    
    nav_h = int(full_light.height * 0.80)
    nav_light = full_light.crop((0, 0, full_light.width, nav_h))
    nav_light_trimmed = nav_light.crop(nav_light.getbbox())
    nav_light_trimmed.save(os.path.join(BRAND_DIR, "quanthire-logo-nav.png"), "PNG", optimize=True)
    
    # Generate and save dark versions
    full_dark = make_dark_variant(full_light)
    full_dark_path = os.path.join(BRAND_DIR, "quanthire-logo-full-dark.png")
    full_dark.save(full_dark_path, "PNG", optimize=True)
    print(f"Saved full dark logo: {full_dark_path} -> {full_dark.size}")
    
    nav_dark = full_dark.crop((0, 0, full_dark.width, nav_h))
    nav_dark_trimmed = nav_dark.crop(nav_dark.getbbox())
    nav_dark_path = os.path.join(BRAND_DIR, "quanthire-logo-nav-dark.png")
    nav_dark_trimmed.save(nav_dark_path, "PNG", optimize=True)
    print(f"Saved nav dark logo: {nav_dark_path} -> {nav_dark_trimmed.size}")

if __name__ == "__main__":
    main()
