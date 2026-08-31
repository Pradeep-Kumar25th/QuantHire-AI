"""
Setup favicon from Favicon.png
Creates optimized favicon files for browser tabs.
"""

from PIL import Image
import os
import shutil

def setup_favicon():
    """Create favicon files from Favicon.png."""
    
    # Paths
    source_favicon = "public/images/LatestFavicon.png"
    favicon_ico = "public/favicon.ico"
    icon_png_app = "src/app/icon.png"
    apple_icon = "public/apple-icon.png"
    
    # Check if source exists
    if not os.path.exists(source_favicon):
        print(f"❌ Source favicon not found at {source_favicon}")
        return False
    
    try:
        print(f"📖 Loading favicon from {source_favicon}...")
        img = Image.open(source_favicon)
        
        # Get original size
        original_size = img.size
        print(f"   Original size: {original_size[0]}x{original_size[1]}")
        
        # Convert RGBA to RGB if necessary (for ICO format)
        if img.mode == 'RGBA':
            # Create transparent background for PNG, white for ICO
            print("   Converting RGBA to RGB for ICO format...")
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img_rgb = background
        else:
            img_rgb = img
        
        # Create favicon.ico (multiple sizes for better compatibility)
        print("🔨 Creating favicon.ico...")
        sizes = [(16, 16), (32, 32), (48, 48)]
        favicon_images = []
        for size in sizes:
            resized = img_rgb.resize(size, Image.Resampling.LANCZOS)
            favicon_images.append(resized)
        
        # Save as ICO
        favicon_images[0].save(
            favicon_ico,
            format='ICO',
            sizes=[(s[0], s[1]) for s in sizes]
        )
        print(f"✅ Created {favicon_ico}")
        
        # Create icon.png for Next.js App Router (32x32)
        print("🔨 Creating icon.png for Next.js App Router...")
        icon_32 = img.resize((32, 32), Image.Resampling.LANCZOS)
        icon_32.save(icon_png_app, format='PNG', optimize=True)
        print(f"✅ Created {icon_png_app}")
        
        # Create apple-icon.png (180x180 for iOS)
        print("🔨 Creating apple-icon.png...")
        apple_icon_img = img.resize((180, 180), Image.Resampling.LANCZOS)
        apple_icon_img.save(apple_icon, format='PNG', optimize=True)
        print(f"✅ Created {apple_icon}")
        
        print("\n" + "="*60)
        print("🎉 Favicon setup complete!")
        print("="*60)
        print("\nFiles created:")
        print(f"  ✅ {favicon_ico} (16x16, 32x32, 48x48)")
        print(f"  ✅ {icon_png_app} (32x32)")
        print(f"  ✅ {apple_icon} (180x180)")
        print("\nThe favicon is now configured in layout.tsx")
        print("Restart your Next.js dev server to see the favicon!")
        
        return True
        
    except ImportError:
        print("❌ PIL/Pillow not installed.")
        print("Install it with: pip install Pillow")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("QuantHire AI - Favicon Setup")
    print("=" * 60)
    print()
    
    setup_favicon()

