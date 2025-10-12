# Yikers Discord Bot

A powerful and feature-rich Discord bot built with Python, focusing on utility, security, gaming, and administration. Comes with a secure CLI-based setup and a real-time web dashboard.

## Core Features

-   **Secure Setup**: Encrypts your bot token and other credentials so you never have to worry about exposing them.
-   **Web Dashboard**: A real-time web interface to monitor bot status, view server activity, and send messages through the bot.
-   **Extensive Commands**: A wide range of commands for administration, games, image manipulation, and general utility.
-   **Customization**: Supports per-server command prefixes and has a simple `.ini` file for global configuration.

## The Web Dashboard

The bot includes a built-in web dashboard that runs alongside it, accessible by default at `http://localhost:5000`.

**Dashboard Features:**

-   **Live Stats**: See real-time latency, server count, and total user count.
-   **Live Channel Viewer**: Select any server and channel the bot is in to view messages in real-time.
-   **Send Messages**: Send text messages and upload images directly to a channel from the web UI.
-   **Live Console Log**: View the bot's console output directly in your browser.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine.

### Prerequisites

-   Python 3.8+
-   Git

### Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/explysm/yikers-discord-bot.git
    cd yikers-discord-bot
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```sh
    python3 -m venv venv
    source venv/bin/activate
    # On Windows, use: venv\Scripts\activate
    ```

3.  **Install the required dependencies:**
    
    ```sh
    pip install -r requirements.txt
    ```

## Configuration and Running the Bot

The bot uses a command-line interface for initial setup and launching.

1.  **Run the main script:**
    ```sh
    python3 bot.py
    ```

2.  **Create the encrypted environment file:**
    -   When the menu appears, select option `1`.
    -   You will be prompted to enter your **Discord Bot Token** and **Discord App ID**.
    -   This will create `key.key` (your encryption key) and `.env.enc` (your encrypted credentials).

    > **IMPORTANT:** Treat your `key.key` file like a password. **Do not share it or commit it to version control.** The `.gitignore` file is already configured to ignore it.

3.  **Start the bot:**
    
    -   Run `python3 bot.py` again and select option `2`.
    -   The bot will use the key to decrypt your credentials and go online.

## Command Reference

The default prefix is `?`. Use `?help` for a list of commands or `?help <command>` for details on a specific command.

### Admin Commands 
-   `?setprefix <new_prefix>`: Sets a new command prefix for the server.
-   `?welcome channel <#channel>`: Sets the channel for welcome messages.
-   `?welcome set`: Interactively sets the server's welcome message.
-   `?welcome test`: Sends a test welcome message.

### Game Commands 
-   `?trivia [category_id]`: Starts a trivia game. 
-   `?trivia categories`: Lists all available trivia categories.
-   `?hm start`: Starts a new hangman game.
-   `?hm <letter/word>`: Makes a guess in the current hangman game.
-   `?hm stop`: Stops the current hangman game.
-   `?leaderboard <game>`: Shows the server leaderboard for a game (e.g., `trivia`, `hangman`). Alias: `?lb`.
-   `?rank [user]`: Shows your game stats or another user's.

### Utility Commands 
-   `?define <word>`: Gets the definition of a word.
-   `?synonym <word>`: Gets synonyms for a word.
-   `?wiki <topic>`: Searches Wikipedia and returns a summary.
-   `?github <user/repo>`: Fetches stats for a GitHub repository. Defaults to `explysm` as the user if not provided.
-   `?tv <query>`: Searches for a TV show and displays its information.
-   `?movie <query>`: Searches for a movie (requires TMDB API key in `bot-settings.ini`).
-   `?survey create "Question"`: Creates a new survey.
-   `?survey respond <id> "Answer"`: Responds to a survey.
-   `?survey view <id>`: Views survey responses.
-   `?survey end <id>`: Ends a survey.
-   `?customcmd add <name> <response>`: Adds a custom text command.
-   `?customcmd delete <name>`: Deletes a custom command.
-   `?customcmd list`: Lists all custom commands.

### Image Commands 
-   `?caption <text>`: Adds a caption to an attached or replied-to image/GIF.
-   `?togif`: Converts an image into a GIF.

### AI Commands
-   `?summary [limit]`: Summarizes recent messages in the channel using AI (requires configuration in `bot-settings.ini`).

### General Commands 
-   `?ping`: Checks the bot's latency.
-   `?userinfo [user]`: Displays information about a user.
-   `?spotify [user]`: Shows what a user is listening to on Spotify.
-   `?search "<query>" [limit]`: Searches recent messages for a query.
-   `?help [command]`: Shows a list of commands or detailed help for one command.

## Important API note

This repo provides an API key for TMDB, but you **will** have to provide your own token for the Ai commands, as they use the hugging face API.

All other API's used do not need a key.
