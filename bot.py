import discord
from discord.ext import commands
import term
from encryption import generate_key, encrypt_file, decrypt_file
import os
import json
import configparser
import asyncio
import threading
import logging

# Import Flask and SocketIO here to centralize control
from flask import Flask
from flask_socketio import SocketIO
# Import the dashboard function that we will configure
from dashboard.app import run_dashboard

is_logging_configured = False

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

# --- Bot Startup ---
async def start_bot():
    """Initializes and runs the Discord bot."""
    logging.info("Attempting to start the bot...")
    if not os.path.exists(".env.enc") or not os.path.exists("key.key"):
        logging.error("Error: .env.enc or key.key not found. Please run option 1 first.")
        return

    # Decrypt .env file
    try:
        key = open("key.key", "rb").read()
        env_content = decrypt_file(".env.enc", key)
        env_lines = env_content.splitlines()
        config = {line.split("=")[0]: line.split("=")[1] for line in env_lines}
    except Exception as e:
        logging.error(f"Error decrypting .env file: {e}")
        return

    if "DISCORD_TOKEN" not in config or not config["DISCORD_TOKEN"]:
        logging.error("Error: DISCORD_TOKEN not found or is empty in .env file.")
        return

    # --- Settings Management ---
    try:
        with open("servers/settings.json", "r") as f:
            bot_settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        bot_settings = {}

    def save_settings():
        os.makedirs("servers", exist_ok=True)
        with open("servers/settings.json", "w") as f:
            json.dump(bot.settings, f, indent=4)

    bot_config = configparser.ConfigParser()
    if not os.path.exists("bot-settings.ini"):
        bot_config['togif'] = {'max_gif_size_mb': '5'}
        bot_config['ai'] = {'features_enabled': 'false', 'huggingface_token': 'YOUR_TOKEN_HERE'}
        with open('bot-settings.ini', 'w') as configfile:
            bot_config.write(configfile)
    bot_config.read("bot-settings.ini")

    try:
        max_gif_size = bot_config.getint('togif', 'max_gif_size_mb', fallback=5) * 1024 * 1024
        ai_enabled = bot_config.getboolean('ai', 'features_enabled', fallback=False)
        hf_token = bot_config.get('ai', 'huggingface_token', fallback='')
        tmdb_api_key = bot_config.get('tmdb', 'api_key', fallback='')
    except (configparser.NoSectionError, configparser.NoOptionError):
        max_gif_size = 5 * 1024 * 1024
        ai_enabled = False
        hf_token = ''
        tmdb_api_key = ''

    # --- Bot Definition ---
    DEFAULT_PREFIX = "?"
    def get_prefix(bot, message):
        if not message.guild:
            return DEFAULT_PREFIX
        guild_settings = bot.settings.get(str(message.guild.id), {})
        return guild_settings.get("prefix", DEFAULT_PREFIX)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    bot = commands.Bot(command_prefix=get_prefix, intents=intents)

    bot.settings = bot_settings
    bot.save_settings = save_settings
    bot.max_gif_size = max_gif_size
    bot.hf_token = hf_token
    bot.tmdb_api_key = tmdb_api_key

    # --- Flask & SocketIO setup ---
    app = Flask(__name__, template_folder='dashboard/templates', static_folder='dashboard/static')
    # Reverted the CORS change for now to fix the startup failure. We can re-evaluate if the JS issue persists.
    socketio = SocketIO(app, async_mode='threading', cors_allowed_origins='*', engineio_logger=False)

    # --- Logging Setup ---
    global is_logging_configured
    if not is_logging_configured:
        class SocketIOHandler(logging.Handler):
            def emit(self, record):
                log_entry = self.format(record)
                socketio.emit('log', {'data': log_entry})

        handler = SocketIOHandler()
        handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s'))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger('discord').setLevel(logging.WARNING)
        logging.getLogger('websockets').setLevel(logging.WARNING)
        is_logging_configured = True

    # --- Start Dashboard Thread ---
    dashboard_thread = threading.Thread(
        target=run_dashboard, 
        args=(bot, asyncio.get_event_loop(), app, socketio),
        daemon=True
    )
    dashboard_thread.start()
    logging.info("Dashboard thread started. Access at http://127.0.0.1:5000")

    @bot.event
    async def on_ready():
        logging.info(f"Logged in as {bot.user}")
        logging.info("Loading cogs...")
        cogs_to_load = os.listdir('./cogs')
        if not ai_enabled:
            logging.info("AI features are disabled. Skipping ai.py.")
            cogs_to_load = [c for c in cogs_to_load if c != 'ai.py']

        for filename in cogs_to_load:
            if filename.endswith('.py'):
                try:
                    await bot.load_extension(f'cogs.{filename[:-3]}')
                    logging.info(f"  - Loaded {filename}")
                except Exception as e:
                    logging.error(f"  - Failed to load {filename}: {e}")
        logging.info("Cogs loaded. Bot is ready.")

    logging.info("Starting bot...")
    await bot.start(config["DISCORD_TOKEN"])

# --- Main Menu ---
def main():
    """Main function to display the CLI menu."""
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
            try:
                asyncio.run(start_bot())
            except KeyboardInterrupt:
                print("\nBot shut down by user.")
            except Exception as e:
                print(f"An error occurred: {e}")
        elif choice == "3":
            break

if __name__ == "__main__":
    main()
