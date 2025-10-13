
import discord
from discord.ext import commands
import json
import os
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import configparser
import io

# --- Helper Functions ---

def get_profile_path(guild_id, user_id):
    return f'servers/profiles/{guild_id}/{user_id}'

def get_profile_data(guild_id, user_id):
    profile_dir = get_profile_path(guild_id, user_id)
    profile_file = f'{profile_dir}/profile.json'
    if not os.path.exists(profile_file):
        # Default profile structure
        return {
            "description": "No description set.",
            "color": "#ffffff",
            "reputation": 0,
            "badges": []
        }
    with open(profile_file, 'r') as f:
        return json.load(f)

def save_profile_data(guild_id, user_id, data):
    profile_dir = get_profile_path(guild_id, user_id)
    os.makedirs(profile_dir, exist_ok=True)
    profile_file = f'{profile_dir}/profile.json'
    with open(profile_file, 'w') as f:
        json.dump(data, f, indent=4)

# --- Cog Class ---

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        config = configparser.ConfigParser()
        config.read('bot-settings.ini')
        self.bg_size_limit_mb = config.getint('profile', 'background_size_limit_mb', fallback=1)
        self.bg_size_limit_bytes = self.bg_size_limit_mb * 1024 * 1024

    # --- Commands ---

    @commands.command(name='profile')
    async def profile(self, ctx, user: discord.Member = None):
        """Displays a user's profile card."""
        user = user or ctx.author

        # Load data
        profile_data = get_profile_data(ctx.guild.id, user.id)
        profile_dir = get_profile_path(ctx.guild.id, user.id)
        bg_image_path = f'{profile_dir}/background.png'

        if not os.path.exists(bg_image_path):
            await ctx.send(f"{user.mention} hasn't set a background image yet! Use `!setbg`.")
            return

        # --- Image Generation ---
        card = Image.open(bg_image_path).convert('RGBA').resize((800, 300))
        overlay = Image.new('RGBA', card.size, (0, 0, 0, 128))
        card.paste(overlay, (0, 0), overlay)

        # Avatar
        async with aiohttp.ClientSession() as session:
            async with session.get(str(user.avatar.url)) as resp:
                avatar_data = await resp.read()
        avatar = Image.open(io.BytesIO(avatar_data)).convert('RGBA').resize((150, 150))
        mask = Image.new('L', avatar.size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0) + avatar.size, fill=255)
        card.paste(avatar, (50, 75), mask)

        # Text
        draw = ImageDraw.Draw(card)
        font_bold = ImageFont.truetype('utils/fonts/OpenSans-Bold.ttf', 36)
        font_regular = ImageFont.truetype('utils/fonts/OpenSans-Regular.ttf', 24)
        
        user_color = profile_data.get('color', '#ffffff')
        draw.text((240, 100), user.display_name, font=font_bold, fill=user_color)
        draw.text((240, 150), profile_data.get('description', 'No description.'), font=font_regular, fill=(220, 220, 220))

        # Stats & Badges
        rep = profile_data.get('reputation', 0)
        
        # --- Load Leaderboard Stats ---
        try:
            with open('servers/leaderboard.json', 'r') as f:
                leaderboard = json.load(f)
            user_stats = leaderboard.get(str(ctx.guild.id), {}).get(str(user.id), {})
            trivia_wins = user_stats.get('trivia_wins', 0)
            hangman_wins = user_stats.get('hangman_wins', 0)
        except FileNotFoundError:
            trivia_wins, hangman_wins = 0, 0

        stats_text = f"Rep: {rep} | Trivia Wins: {trivia_wins} | Hangman Wins: {hangman_wins}"
        draw.text((240, 200), stats_text, font=font_regular, fill=(220, 220, 220))

        # --- Badge Logic ---
        badge_x = 240
        if trivia_wins >= 5:
            # In a real scenario, you'd load a badge image. For now, we'll draw a placeholder.
            draw.rectangle((badge_x, 240, badge_x + 30, 270), fill=('gold'))
            draw.text((badge_x + 5, 245), "T", font=font_regular, fill=('black'))
            badge_x += 40
        if hangman_wins >= 5:
            draw.rectangle((badge_x, 240, badge_x + 30, 270), fill=('silver'))
            draw.text((badge_x + 5, 245), "H", font=font_regular, fill=('black'))


        # Save and send
        final_card_path = f'{profile_dir}/profile_card.png'
        card.save(final_card_path)
        await ctx.send(file=discord.File(final_card_path))

    @commands.command(name='setbg')
    async def set_background(self, ctx):
        """Sets your profile background. Must be under the size limit."""
        if not ctx.message.attachments:
            await ctx.send("You need to upload an image with the command!")
            return

        attachment = ctx.message.attachments[0]
        if not attachment.content_type.startswith('image/'):
            await ctx.send("The attached file must be an image.")
            return

        if attachment.size > self.bg_size_limit_bytes:
            await ctx.send(f"Image is too large! The size limit is {self.bg_size_limit_mb}MB.")
            return

        profile_dir = get_profile_path(ctx.guild.id, ctx.author.id)
        os.makedirs(profile_dir, exist_ok=True)
        await attachment.save(f'{profile_dir}/background.png')
        await ctx.send("Your background has been updated!")

    @commands.command(name='setdesc')
    async def set_description(self, ctx, *, description: str):
        """Sets your profile description (max 100 chars)."""
        if len(description) > 100:
            await ctx.send("Your description must be 100 characters or less.")
            return
        
        data = get_profile_data(ctx.guild.id, ctx.author.id)
        data['description'] = description
        save_profile_data(ctx.guild.id, ctx.author.id, data)
        await ctx.send("Your description has been updated!")

    @commands.command(name='setcolor')
    async def set_color(self, ctx, color: str):
        """Sets your profile name color using a hex code (e.g., #ff0000)."""
        if not color.startswith('#') or len(color) != 7:
            await ctx.send("Invalid hex code. Please use the format `#xxxxxx`.")
            return
        
        data = get_profile_data(ctx.guild.id, ctx.author.id)
        data['color'] = color
        save_profile_data(ctx.guild.id, ctx.author.id, data)
        await ctx.send(f"Your color has been set to {color}!")

    @commands.command(name='rep')
    @commands.cooldown(1, 86400, commands.BucketType.user) # 1 rep per user per day
    async def give_reputation(self, ctx, user: discord.Member):
        """Gives a reputation point to another user."""
        if user == ctx.author:
            await ctx.send("You can't give reputation to yourself.")
            return

        data = get_profile_data(ctx.guild.id, user.id)
        data['reputation'] = data.get('reputation', 0) + 1
        save_profile_data(ctx.guild.id, user.id, data)
        await ctx.send(f"You have given a reputation point to {user.mention}!")

    @give_reputation.error
    async def rep_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"You can give another rep point in {int(error.retry_after / 3600)} hours.")

async def setup(bot):
    await bot.add_cog(Profile(bot))
