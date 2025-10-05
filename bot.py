import discord
from discord.ext import commands
import term
from encryption import generate_key, encrypt_file, decrypt_file
import os
import json
import typing
import asyncio
import io
import aiohttp
from PIL import Image # Only Image is needed here for Image.open check

from image_utils import get_font, add_caption_to_image

# --- Terminal UI Functions ---
def print_banner(text):
    """Prints a banner with the given text."""
    term.writeLine(term.format(text, term.bold, term.green))

def print_menu(menu):
    """Prints a menu from a dictionary."""
    for key, value in menu.items():
        term.writeLine(f"{term.format(key, term.bold)}: {value}")

def get_choice(choices):
    """Gets a choice from the user."""
    while True:
        choice = input("> ")
        if choice in choices:
            return choice
        else:
            term.writeLine("Invalid choice.", term.red)

# --- .env and Encryption Functions ---
def create_env_file():
    """Creates an encrypted .env file."""
    token = input("Enter your Discord Bot Token: ")
    app_id = input("Enter your Discord App ID: ")
    with open(".env", "w") as f:
        f.write(f"DISCORD_TOKEN={token}\n")
        f.write(f"APP_ID={app_id}\n")
    
    key = generate_key()
    encrypt_file(".env", key)
    with open("key.key", "wb") as key_file:
        key_file.write(key)
    print("Encrypted .env file created as .env.enc")
    print("Encryption key saved as key.key. DO NOT SHARE THIS KEY.")

# --- Bot ---
def start_bot():
    """Starts the Discord bot."""
    print("Attempting to start the bot...")
    if not os.path.exists(".env.enc") or not os.path.exists("key.key"):
        print("Error: .env.enc or key.key not found.")
        return

    print("Found .env.enc and key.key.")
    
    key = None
    with open("key.key", "rb") as key_file:
        key = key_file.read()
    
    if not key:
        print("Error: key.key is empty.")
        return
        
    print("Successfully read key from key.key.")

    try:
        env_content = decrypt_file(".env.enc", key)
        env_lines = env_content.splitlines()
        if not env_lines:
            print("Error: Decrypted .env file is empty.")
            return
        config = {line.split("=")[0]: line.split("=")[1] for line in env_lines}
        print("Successfully decrypted and parsed .env file.")
    except Exception as e:
        print(f"Error decrypting .env file: {e}")
        return

    if "DISCORD_TOKEN" not in config or not config["DISCORD_TOKEN"]:
        print("Error: DISCORD_TOKEN not found or is empty in .env file.")
        return

    print("DISCORD_TOKEN found. Initializing bot...")

    # --- Settings Management ---
    settings = {}
    DEFAULT_PREFIX = "?"

    def save_settings():
        with open("settings.json", "w") as f:
            json.dump(settings, f, indent=4)

    try:
        with open("settings.json", "r") as f:
            settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        settings = {}

    def get_prefix(bot, message):
        if not message.guild:
            return DEFAULT_PREFIX
        guild_settings = settings.get(str(message.guild.id), {})
        return guild_settings.get("prefix", DEFAULT_PREFIX)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

    # --- Events ---
    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user}")

    @bot.event
    async def on_member_join(member):
        guild_id = str(member.guild.id)
        guild_settings = settings.get(guild_id, {})
        
        welcome_channel_id = guild_settings.get("welcome_channel_id")
        welcome_message = guild_settings.get("welcome_message")

        if welcome_channel_id and welcome_message:
            channel = member.guild.get_channel(welcome_channel_id)
            if channel:
                formatted_message = welcome_message.replace("<<user>>", member.mention)
                await channel.send(formatted_message)

    # --- Commands ---
    @bot.command()
    async def ping(ctx):
        """Gets the bot's latency."""
        latency = bot.latency * 1000  # in ms
        embed = discord.Embed(title="Pong!", description=f"Latency: {latency:.2f}ms", color=discord.Color.blue())
        await ctx.send(embed=embed)

    @bot.command()
    @commands.has_permissions(manage_guild=True)
    async def setprefix(ctx, prefix: str):
        """Sets the bot's prefix for this server."""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return
        guild_id = str(ctx.guild.id)
        if guild_id not in settings:
            settings[guild_id] = {}
        settings[guild_id]["prefix"] = prefix
        save_settings()
        await ctx.send(f"Prefix for this server has been set to `{prefix}`")

    @setprefix.error
    async def setprefix_error(ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to do that.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Please provide a prefix.")

    @bot.command()
    async def userinfo(ctx, user: typing.Union[discord.Member, discord.User] = None):
        """Displays information about a user."""
        user = user or ctx.author
        embed = discord.Embed(title=f"User Info: {user.name}", color=user.color)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="ID", value=user.id, inline=False)
        embed.add_field(name="Created At", value=user.created_at.strftime("%b %d, %Y"), inline=True)
        
        if isinstance(user, discord.Member):
            embed.add_field(name="Joined At", value=user.joined_at.strftime("%b %d, %Y"), inline=True)
            roles = [role.mention for role in user.roles[1:]]
            if roles:
                embed.add_field(name=f"Roles ({len(roles)})", value=", ".join(roles), inline=False)

        await ctx.send(embed=embed)

    @bot.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def welcome(ctx):
        """Welcome message management commands."""
        await ctx.send("Invalid welcome command. Use `?welcome set`, `?welcome channel`, or `?welcome test`.")

    @welcome.command()
    @commands.has_permissions(manage_guild=True)
    async def set(ctx):
        """Sets the welcome message for this server."""
        await ctx.send('''Please send the welcome message. (Tip: use "<<user>>" to mention the user)''')
        
        try:
            message = await bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=300.0)
        except asyncio.TimeoutError:
            await ctx.send("You took too long to respond.")
            return

        guild_id = str(ctx.guild.id)
        if guild_id not in settings:
            settings[guild_id] = {}
        settings[guild_id]["welcome_message"] = message.content
        save_settings()
        await ctx.send("Welcome message has been set.")

    @welcome.command()
    @commands.has_permissions(manage_guild=True)
    async def channel(ctx, channel: discord.TextChannel):
        """Sets the welcome channel for this server."""
        guild_id = str(ctx.guild.id)
        if guild_id not in settings:
            settings[guild_id] = {}
        settings[guild_id]["welcome_channel_id"] = channel.id
        save_settings()
        await ctx.send(f"Welcome channel has been set to {channel.mention}")

    @welcome.command()
    @commands.has_permissions(manage_guild=True)
    async def test(ctx):
        """Tests the welcome message."""
        guild_id = str(ctx.guild.id)
        guild_settings = settings.get(guild_id, {})
        
        welcome_channel_id = guild_settings.get("welcome_channel_id")
        welcome_message = guild_settings.get("welcome_message")

        if welcome_channel_id and welcome_message:
            channel = ctx.guild.get_channel(welcome_channel_id)
            if channel:
                formatted_message = welcome_message.replace("<<user>>", ctx.author.mention)
                await channel.send(f"**Test Welcome Message:**\n{formatted_message}")
            else:
                await ctx.send("Welcome channel not found.")
        else:
            await ctx.send("Welcome message or channel not set.")
            
    @bot.command()
    async def help(ctx):
        """Shows this help message."""
        embed = discord.Embed(title="Bot Commands", color=discord.Color.blue())
        
        for command in bot.commands:
            if command.name != 'help':
                embed.add_field(name=f"{get_prefix(bot, ctx.message)}{command.name} {command.signature}", value=command.help or "No description", inline=False)
        
        await ctx.send(embed=embed)

    @bot.command()
    async def caption(ctx, *, text: typing.Optional[str] = None):
        """Adds a caption to an image or GIF."""
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
                    content_type = resp.headers.get("Content-Type", "").lower()
                    image_bytes = await resp.read()

            # --- DEBUGGING ---
            print(f"DEBUG: Image URL: {image_url}")
            print(f"DEBUG: Content-Type: {content_type}")
            print(f"DEBUG: Image bytes start: {image_bytes[:10]}")
            # --- END DEBUGGING ---

            is_animated_image = False
            try:
                img_check = Image.open(io.BytesIO(image_bytes))
                if hasattr(img_check, 'is_animated') and img_check.is_animated:
                    is_animated_image = True
            except IOError:
                pass # Not an image Pillow can open

            loop = asyncio.get_event_loop()
            result_bytes = await loop.run_in_executor(None, add_caption_to_image, image_bytes, text or "", is_animated_image)

            if result_bytes:
                filename = "captioned.gif" if is_animated_image else "captioned.png"
                file = discord.File(fp=io.BytesIO(result_bytes), filename=filename)
                await ctx.send(file=file)
            else:
                await ctx.send("Could not process the image. It might be an unsupported format.")

        except Exception as e:
            print(f"Error in caption command: {e}")
            await ctx.send("An error occurred while processing the image.")


    print("Starting bot...")
    bot.run(config["DISCORD_TOKEN"])
    print("Bot has stopped.")

# --- Main ---
def main():
    """Main function to display the GUI."""
    term.clear()
    print_banner("YikeGames Discord Bot")
    
    while True:
        print_menu({
            "1": "Create Encrypted .env",
            "2": "Start Bot",
            "3": "Exit"
        })
        choice = get_choice(["1", "2", "3"])

        if choice == "1":
            create_env_file()
        elif choice == "2":
            start_bot()
        elif choice == "3":
            break

if __name__ == "__main__":
    main()
