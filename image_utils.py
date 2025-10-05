import io
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageSequence

def get_font(size):
    font_paths = [
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

def add_caption_to_image(image_bytes, text, is_animated_image=False):
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except IOError:
        return None

    # --- Dynamic Font Size ---
    font_size = int(img.width / 15)
    if font_size < 20:
        font_size = 20
    font = get_font(font_size)

    # --- Word Wrap ---
    wrapper = textwrap.TextWrapper(width=30) # Adjust width for best results
    wrapped_text = wrapper.fill(text=text)

    # --- Calculate new height ---
    padding = 20 # Increased padding for taller bar
    dummy_draw = ImageDraw.Draw(Image.new('RGBA', (1,1)))
    text_bbox = dummy_draw.multiline_textbbox((0, 0), wrapped_text, font=font, align="center")
    text_height = text_bbox[3] - text_bbox[1]
    caption_height = text_height + (3 * padding) # More padding for height

    if is_animated_image:
        frames = []
        duration = img.info.get('duration', 100)
        loop = img.info.get('loop', 0)

        for frame in ImageSequence.Iterator(img):
            frame = frame.convert("RGBA")
            
            new_frame = Image.new("RGBA", (frame.width, frame.height + caption_height), "white")
            new_frame.paste(frame, (0, caption_height)) # Paste original frame below caption bar

            draw = ImageDraw.Draw(new_frame)
            # Calculate text position for centering
            text_width = text_bbox[2] - text_bbox[0] # Use the width from the dummy calculation
            text_x = (new_frame.width - text_width) / 2
            text_y = padding

            draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill="black", align="center")
            
            frames.append(new_frame)
        
        output_buffer = io.BytesIO()
        frames[0].save(output_buffer, format='GIF', save_all=True, append_images=frames[1:], loop=loop, duration=duration)
        return output_buffer.getvalue()

    else: # Static image
        img = img.convert("RGBA")
        new_img = Image.new("RGBA", (img.width, img.height + caption_height), "white")
        new_img.paste(img, (0, caption_height)) # Paste original image below caption bar

        draw = ImageDraw.Draw(new_img)
        # Calculate text position for centering
        text_width = text_bbox[2] - text_bbox[0] # Use the width from the dummy calculation
        text_x = (new_img.width - text_width) / 2
        text_y = padding

        draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill="black", align="center")

        output_buffer = io.BytesIO()
        new_img.save(output_buffer, format='PNG')
        return output_buffer.getvalue()