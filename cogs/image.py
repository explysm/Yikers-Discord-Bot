import discord
from discord.ext import commands
import typing
import asyncio
import io
import aiohttp
import logging
from PIL import Image

from utils.image_utils import add_caption_to_image, convert_to_gif

class ImageCog(commands.Cog, name="Image"):
    """Commands for image manipulation."""
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def caption(self, ctx, *, text: str):
        """Adds a caption to an image or GIF. Optionally add a number at the end to scale the font (e.g., ..."my caption" 1.5)."""
        loading_msg = await ctx.send(f"Adding caption... (Latency: {self.bot.latency * 1000:.2f}ms)")
        args = text.split()
        multiplier = 1.0
        caption_text = text

        if args:
            try:
                last_arg = float(args[-1])
                if last_arg > 0:
                    multiplier = last_arg
                    caption_text = " ".join(args[:-1])
            except (ValueError, IndexError):
                # Last arg is not a number, so it's part of the caption
                pass

        if not caption_text:
            await ctx.send("Please provide text for the caption.")
            return

        image_url = None
        if ctx.message.attachments:
            image_url = ctx.message.attachments[0].url
        elif ctx.message.reference:
            ref_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref_message.attachments:
                image_url = ref_message.attachments[0].url
            elif ref_message.embeds:
                for embed in ref_message.embeds:
                    if embed.image:
                        image_url = embed.image.url
                        break
                    elif embed.thumbnail:
                        image_url = embed.thumbnail.url
                        break

        if not image_url:
            await ctx.send("Please provide an image to caption (either as an attachment or by replying to a message with an image).")
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status != 200:
                        await ctx.send("Could not download the image.")
                        return
                    image_bytes = await resp.read()

            is_animated_image = False
            try:
                img_check = Image.open(io.BytesIO(image_bytes))
                if hasattr(img_check, 'is_animated') and img_check.is_animated:
                    is_animated_image = True
            except IOError:
                pass

            loop = asyncio.get_event_loop()
            result_bytes = await loop.run_in_executor(None, add_caption_to_image, image_bytes, caption_text, is_animated_image, multiplier)

            if result_bytes:
                filename = "captioned.gif" if is_animated_image else "captioned.png"
                file = discord.File(fp=io.BytesIO(result_bytes), filename=filename)
                await loading_msg.delete()
                await ctx.send(file=file)
            else:
                await ctx.send("Could not process the image. It might be an unsupported format.")

        except Exception as e:
            logging.error(f"Error in caption command: {e}")
            await ctx.send("An error occurred while processing the image.")

    @commands.command()
    async def togif(self, ctx):
        """Converts an image into a GIF."""
        media_url = None
        filename = "source"

        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]
            if attachment.content_type and 'video' in attachment.content_type:
                await ctx.send("This command no longer supports video conversion.")
                return
            media_url = attachment.url
            if attachment.filename:
                filename = attachment.filename

        elif ctx.message.reference:
            ref_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref_message.attachments:
                attachment = ref_message.attachments[0]
                if attachment.content_type and 'video' in attachment.content_type:
                    await ctx.send("This command no longer supports video conversion.")
                    return
                media_url = attachment.url
                if attachment.filename:
                    filename = attachment.filename
            elif ref_message.embeds:
                for embed in ref_message.embeds:
                    if embed.video:
                        await ctx.send("This command no longer supports video conversion.")
                        return
                    elif embed.image:
                        media_url = embed.image.url
                        break
                    elif embed.thumbnail:
                        media_url = embed.thumbnail.url
                        break
        
        if not media_url:
            await ctx.send("Please provide an image to convert (either as an attachment or by replying to a message).")
            return

        status_message = await ctx.send(f"Processing `{filename}`... this may take a moment.")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(media_url) as resp:
                    if resp.status != 200:
                        await ctx.send("Could not access the image file.")
                        return
                    size = resp.headers.get('Content-Length')
                    if size and int(size) > 25 * 1024 * 1024:
                        await ctx.send("The source image is too large to process (must be under 25MB).")
                        return

                async with session.get(media_url) as resp:
                    if resp.status != 200:
                        await ctx.send("Could not download the image file.")
                        return
                    media_bytes = await resp.read()

            loop = asyncio.get_event_loop()
            result_bytes, error_message = await loop.run_in_executor(
                None, 
                convert_to_gif, 
                media_bytes, 
                self.bot.max_gif_size
            )

            if error_message:
                await status_message.edit(content=f"Error: {error_message}")
                return

            if result_bytes:
                file = discord.File(fp=io.BytesIO(result_bytes), filename="converted.gif")
                await status_message.delete()
                await ctx.send(file=file)
            else:
                await status_message.edit(content="Could not convert to GIF. The format might be unsupported.")

        except Exception as e:
            logging.error(f"Error in togif command: {e}")
            await status_message.edit(content="An unexpected error occurred during conversion.")

async def setup(bot):
    await bot.add_cog(ImageCog(bot))
