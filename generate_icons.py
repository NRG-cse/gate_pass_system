# generate_icons.py - FIXED FOR WINDOWS
from PIL import Image, ImageDraw, ImageFont
import os

def generate_icons():
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    # Icon directory create
    os.makedirs('static/icons', exist_ok=True)
    
    for size in sizes:
        # Create image with blue background
        img = Image.new('RGB', (size, size), color=(52, 152, 219))
        draw = ImageDraw.Draw(img)
        
        # Add text "GP"
        try:
            font_size = size // 3
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        text = "GP"
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        position = ((size - text_width) // 2, (size - text_height) // 2)
        draw.text(position, text, fill=(255, 255, 255), font=font)
        
        # Save icon
        img.save(f'static/icons/icon-{size}x{size}.png')
        print(f"Generated icon-{size}x{size}.png")  # Removed Unicode character
    
    print("All icons generated successfully!")  # Removed Unicode character

if __name__ == '__main__':
    generate_icons()