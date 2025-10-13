import io
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageSequence

def get_font(size):
    font_paths = [
        "utils/fonts/OpenSans-Bold.ttf",
        "utils/fonts/OpenSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "arialbd.ttf", # Arial Bold
        "arial.ttf"
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except IOError:
            continue
    return ImageFont.load_default()

def add_caption_to_image(image_bytes, text, is_animated_image=False, multiplier=1.0):
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except IOError:
        return None

    # --- Dynamic Font Size & Wrapping ---
    # Apply the multiplier to the initial font size calculation
    font_size = int((img.width / 10) * multiplier)
    padding = int(img.width * 0.04) # 4% padding on each side
    drawable_width = img.width - (2 * padding)

    while font_size > 10: # Don't let the font get too small
        font = get_font(font_size)
        
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        avg_char_width = font.getlength(alphabet) / len(alphabet)
        if avg_char_width == 0: avg_char_width = 1

        wrap_width = int(drawable_width / avg_char_width)
        if wrap_width <= 1:
            font_size -= 2
            continue

        wrapper = textwrap.TextWrapper(width=wrap_width, break_long_words=True)
        wrapped_text = wrapper.fill(text=text)

        dummy_draw = ImageDraw.Draw(Image.new('RGBA', (1,1)))
        text_bbox = dummy_draw.multiline_textbbox((0, 0), wrapped_text, font=font, align="center")
        text_width = text_bbox[2] - text_bbox[0]

        if text_width <= drawable_width:
            break
        else:
            font_size -= 2
    else:
        pass

    # --- Calculate new height ---
    text_height = text_bbox[3] - text_bbox[1]
    caption_padding = int(font_size * 0.5)
    caption_height = text_height + (2 * caption_padding)

    if is_animated_image:
        frames = []
        duration = img.info.get('duration', 100)
        loop = img.info.get('loop', 0)

        for frame in ImageSequence.Iterator(img):
            frame = frame.convert("RGBA")
            
            new_frame = Image.new("RGBA", (frame.width, frame.height + caption_height), "white")
            new_frame.paste(frame, (0, caption_height))

            draw = ImageDraw.Draw(new_frame)
            # Corrected centering logic
            text_x = ((img.width - text_width) / 2) - text_bbox[0]
            text_y = caption_padding

            draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill="black", align="center")
            
            frames.append(new_frame)
        
        output_buffer = io.BytesIO()
        frames[0].save(output_buffer, format='GIF', save_all=True, append_images=frames[1:], loop=loop, duration=duration)
        return output_buffer.getvalue()

    else: # Static image
        img = img.convert("RGBA")
        new_img = Image.new("RGBA", (img.width, img.height + caption_height), "white")
        new_img.paste(img, (0, caption_height))

        draw = ImageDraw.Draw(new_img)
        # Corrected centering logic
        text_x = ((img.width - text_width) / 2) - text_bbox[0]
        text_y = caption_padding

        draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill="black", align="center")

        output_buffer = io.BytesIO()
        new_img.save(output_buffer, format='PNG')
        return output_buffer.getvalue()

def convert_to_gif(media_bytes, max_size_bytes):
    """Converts an image into a GIF, respecting size limits."""
    try:
        img = Image.open(io.BytesIO(media_bytes))

        # If it's already a GIF, just check the size and return it
        if hasattr(img, 'is_animated') and img.is_animated:
            if len(media_bytes) > max_size_bytes:
                return None, f"The source GIF is too large (>{max_size_bytes / 1024 / 1024:.1f}MB)."
            return media_bytes, None

        output_buffer = io.BytesIO()
        img.save(output_buffer, format='GIF')
        gif_bytes = output_buffer.getvalue()

        if len(gif_bytes) > max_size_bytes:
            return None, f"The resulting GIF is too large (>{max_size_bytes / 1024 / 1024:.1f}MB)."

        return gif_bytes, None
    except IOError:
        return None, "Could not process the image. It might be an unsupported format."