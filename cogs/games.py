import discord
from discord.ext import commands
import aiohttp
import asyncio
import random
import html
import os
import json
from datetime import datetime, timedelta

class Games(commands.Cog):
    """Commands for playing games and checking ranks."""
    def __init__(self, bot):
        self.bot = bot
        self.hangman_games = {}  # {channel_id: game_state}
        self.story_games = {}  # {channel_id: story_state}
        self.words = self._load_words()
        self.leaderboard_file = "servers/leaderboard.json"
        self.leaderboard = self._load_leaderboard()

    # --- Data Loading --- #
    def _load_words(self):
        words_path = 'servers/words.txt'
        if not os.path.exists(words_path):
            return ["python", "discord", "bot", "hangman", "trivia"]
        with open(words_path, 'r') as f:
            words = [line.strip().lower() for line in f if line.strip() and len(line.strip()) > 3 and line.strip().isalpha()]
        return words if words else ["python", "discord", "bot"]

    def _load_leaderboard(self):
        if os.path.exists(self.leaderboard_file):
            with open(self.leaderboard_file, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _save_leaderboard(self):
        os.makedirs("servers", exist_ok=True)
        with open(self.leaderboard_file, 'w') as f:
            json.dump(self.leaderboard, f, indent=4)

    # --- Score Handling --- #
    def _update_score(self, guild_id, user_id, game: str):
        gid = str(guild_id)
        uid = str(user_id)
        
        if gid not in self.leaderboard:
            self.leaderboard[gid] = {}
        if uid not in self.leaderboard[gid]:
            self.leaderboard[gid][uid] = {"trivia_wins": 0, "hangman_wins": 0}
            
        if game == "trivia":
            self.leaderboard[gid][uid]["trivia_wins"] += 1
        elif game == "hangman":
            self.leaderboard[gid][uid]["hangman_wins"] += 1
            
        self._save_leaderboard()

    # --- Trivia --- #
    async def _fetch_json(self, url):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                print(f"API request failed for {url}: {e}")
                return None

    @commands.group(invoke_without_command=True)
    async def trivia(self, ctx, category_id: int = None):
        """Starts a trivia game. Optionally specify a category ID."""
        api_url = "https://opentdb.com/api.php?amount=1&type=multiple"
        if category_id:
            api_url += f"&category={category_id}"

        data = await self._fetch_json(api_url)
        if not data or not data.get("results"):
            await ctx.send("Could not fetch a trivia question. Please try again later.")
            return

        question_data = data["results"][0]
        question = html.unescape(question_data["question"])
        correct_answer = html.unescape(question_data["correct_answer"])
        options = [html.unescape(o) for o in question_data["incorrect_answers"]]
        options.append(correct_answer)
        random.shuffle(options)

        embed = discord.Embed(
            title="🧠 Trivia Time!",
            description=f"**{question}**\n\n" + "\n".join(f"**{i+1}.** {opt}" for i, opt in enumerate(options)),
            color=discord.Color.purple()
        )
        embed.set_footer(text=f"Category: {question_data['category']} | Difficulty: {question_data['difficulty'].capitalize()}")
        
        game_message = await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit() and 1 <= int(m.content) <= len(options)

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=30.0)
            user_answer = options[int(msg.content) - 1]

            if user_answer == correct_answer:
                self._update_score(ctx.guild.id, ctx.author.id, "trivia")
                await game_message.reply(f"Correct! 🎉 The answer was **{correct_answer}**.")
            else:
                await game_message.reply(f"Sorry, that's incorrect. The correct answer was **{correct_answer}**.")
        except asyncio.TimeoutError:
            await game_message.reply(f"Time's up! The correct answer was **{correct_answer}**.")
        except (ValueError, IndexError):
            await game_message.reply("Invalid input. Please enter a number corresponding to an answer.")

    # --- Hangman --- #
    @commands.group(name="hangman", aliases=["hm"], invoke_without_command=True)
    async def hangman(self, ctx, *, guess: str = None):
        """Makes a guess in the current hangman game or shows the current status."""
        channel_id = ctx.channel.id
        if channel_id not in self.hangman_games:
            await ctx.send("No hangman game is currently running in this channel. Use `?hm start` to begin.")
            return

        if guess is None:
            await self._update_hangman_message(ctx)
            return
            
        game = self.hangman_games[channel_id]
        guess = guess.lower()

        # Prevent guessing if the game is already won or lost
        if game['wrong_guesses'] >= 6 or "".join(game['display']) == game['word']:
            await ctx.send("The game is over. Please start a new one.")
            return

        # Validate the guess
        if not guess.isalpha() or len(guess) != 1:
            await ctx.send("Please guess a single letter.")
            return
        if guess in game['guessed_letters']:
            await ctx.send(f"You've already guessed `{guess}`.")
            return

        game['guessed_letters'].add(guess)

        if guess in game['word']:
            # Correct guess
            new_display = ""
            for i, letter in enumerate(game['word']):
                if letter == guess or game['display'][i] != '_':
                    new_display += letter
                else:
                    new_display += "_"
            game['display'] = list(new_display)
        else:
            # Incorrect guess
            game['wrong_guesses'] += 1

        # Update the game message
        await self._update_hangman_message(ctx)

        # Check for win/loss
        if "".join(game['display']) == game['word']:
            self._update_score(ctx.guild.id, ctx.author.id, "hangman")
            await ctx.send(f"Congratulations! You guessed the word: **{game['word']}**")
            del self.hangman_games[channel_id]
        elif game['wrong_guesses'] >= 6:
            await ctx.send(f"You lost! The word was **{game['word']}**.")
            del self.hangman_games[channel_id]

    # --- Leaderboard Commands --- #
    @commands.command(name="leaderboard", aliases=["lb"])
    async def leaderboard_cmd(self, ctx, game: str = None):
        """Shows the server leaderboard for a game. Usage: ?lb <trivia|hangman>"""
        if game not in ["trivia", "hangman"]:
            await ctx.send("Please specify a game for the leaderboard: `trivia` or `hangman`.")
            return

        gid = str(ctx.guild.id)
        if gid not in self.leaderboard or not self.leaderboard[gid]:
            await ctx.send("There are no scores on the leaderboard for this server yet.")
            return

        key = f"{game}_wins"
        
        # Sort users by score for the specified game
        sorted_users = sorted(
            self.leaderboard[gid].items(), 
            key=lambda item: item[1].get(key, 0), 
            reverse=True
        )

        embed = discord.Embed(title=f"🏆 Leaderboard for {game.capitalize()}", color=discord.Color.gold())
        
        description = ""
        for i, (uid, scores) in enumerate(sorted_users[:10]):
            try:
                user = await self.bot.fetch_user(int(uid))
                user_name = user.name
            except discord.NotFound:
                user_name = f"User ID: {uid}"
            
            score = scores.get(key, 0)
            rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"**#{i+1}**"
            description += f"{rank_emoji} {user_name} - {score} wins\n"

        if not description:
            await ctx.send(f"No one has played {game} yet!")
            return

        embed.description = description
        await ctx.send(embed=embed)

    @commands.command(name="rank")
    async def rank_cmd(self, ctx, user: discord.Member = None):
        """Shows your game stats or another user's. Usage: ?rank [@user]"""
        target_user = user or ctx.author
        gid = str(ctx.guild.id)
        uid = str(target_user.id)

        user_scores = self.leaderboard.get(gid, {}).get(uid, None)

        if not user_scores:
            await ctx.send(f"{target_user.display_name} hasn't played any games yet.")
            return

        embed = discord.Embed(title=f"Game Stats for {target_user.display_name}", color=target_user.color)
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.add_field(name="🧠 Trivia Wins", value=user_scores.get("trivia_wins", 0), inline=False)
        embed.add_field(name="🪢 Hangman Wins", value=user_scores.get("hangman_wins", 0), inline=False)

        await ctx.send(embed=embed)

    @trivia.command(name="categories")
    async def trivia_categories(self, ctx):
        """Lists all available trivia categories."""
        data = await self._fetch_json("https://opentdb.com/api_category.php")
        if not data or not data.get("trivia_categories"):
            await ctx.send("Could not fetch trivia categories.")
            return

        embed = discord.Embed(
            title="🧠 Trivia Categories",
            color=discord.Color.purple()
        )
        
        description = ""
        for cat in data["trivia_categories"]:
            description += f"**{cat['id']}**: {cat['name']}\n"
        
        embed.description = description
        embed.set_footer(text="Use `?trivia <id>` to play a specific category.")
        await ctx.send(embed=embed)

    def _get_hangman_drawing(self, wrong_guesses):
        stages = [
            r'''
               -----
               |   |
                   |
                   |
                   |
                   |
            ---------
            ''',
            r'''
               -----
               |   |
               O   |
                   |
                   |
                   |
            ---------
            ''',
            r'''
               -----
               |   |
               O   |
               |   |
                   |
                   |
            ---------
            ''',
            r'''
               -----
               |   |
               O   |
              /|   |
                   |
                   |
            ---------
            ''',
            r'''
               -----
               |   |
               O   |
              /|\  |
                   |
                   |
            ---------
            ''',
            r'''
               -----
               |   |
               O   |
              /|\  |
              /    |
                   |
            ---------
            ''',
            r'''
               -----
               |   |
               O   |
              /|\  |
              / \  |
                   |
            ---------
            '''
        ]
        return f"```\n{stages[wrong_guesses]}\n```"

    async def _update_hangman_message(self, ctx):
        """Edits the hangman message to reflect the current game state."""
        channel_id = ctx.channel.id
        if channel_id not in self.hangman_games:
            return

        game = self.hangman_games[channel_id]
        drawing = self._get_hangman_drawing(game['wrong_guesses'])
        word_display = " ".join(game['display'])
        guessed_letters_str = ", ".join(sorted(game['guessed_letters']))

        embed = discord.Embed(
            title="🪢 Hangman",
            color=discord.Color.blue()
        )
        embed.description = f"{drawing}\n**Word:** `{word_display}`\n\n**Guessed:** {guessed_letters_str}"
        
        if 'message_id' not in game or game['message_id'] is None:
            msg = await ctx.send(embed=embed)
            game['message_id'] = msg.id
        else:
            try:
                msg = await ctx.channel.fetch_message(game['message_id'])
                await msg.edit(embed=embed)
            except discord.NotFound:
                # If message is deleted, send a new one
                msg = await ctx.send(embed=embed)
                game['message_id'] = msg.id

    @hangman.command(name="start")
    async def hm_start(self, ctx):
        """Starts a new hangman game."""
        channel_id = ctx.channel.id
        if channel_id in self.hangman_games:
            await ctx.send("A hangman game is already in progress in this channel. Use `?hm stop` to end it.")
            return

        word = random.choice(self.words)
        self.hangman_games[channel_id] = {
            'word': word,
            'display': ['_'] * len(word),
            'wrong_guesses': 0,
            'guessed_letters': set(),
            'message_id': None
        }

        await ctx.send(f"A new hangman game has started! The word has {len(word)} letters. Use `?hm <letter>` to guess.")
        await self._update_hangman_message(ctx)

    @hangman.command(name="stop")
    async def hm_stop(self, ctx):
        """Stops the current hangman game."""
        channel_id = ctx.channel.id
        if channel_id in self.hangman_games:
            del self.hangman_games[channel_id]
            await ctx.send("The hangman game has been stopped.")
        else:
            await ctx.send("There is no hangman game to stop in this channel.")

    # --- Story Telling Game --- #

    async def _update_story_message(self, ctx):
        game = self.story_games.get(ctx.channel.id)
        if not game:
            return

        story_text = ""
        for i, (author_id, author_name, sentence) in enumerate(game['sentences']):
            story_text += f"**{i+1}. {author_name}:** {sentence}\n"

        embed = discord.Embed(title="✍️ Collaborative Story", description=story_text, color=discord.Color.dark_green())

        count = len(game['sentences'])
        limit = game['limit']

        if count < limit and game.get('turn_user_id'):
            try:
                next_user = await self.bot.fetch_user(game['turn_user_id'])
                footer_text = f"It's {next_user.display_name}'s turn! Use `?story add <sentence>`.\n"
                footer_text += f"If they're AFK, use `?story take` after 5 minutes to steal the turn.\n"
            except discord.NotFound:
                footer_text = "Could not find the next user. The story might be stuck.\n"
        else:
            footer_text = "The story has ended!\n"

        footer_text += f"Progress: {count}/{limit}"
        embed.set_footer(text=footer_text)

        if game.get('message_id'):
            try:
                msg = await ctx.channel.fetch_message(game['message_id'])
                await msg.edit(embed=embed)
            except discord.NotFound:
                msg = await ctx.send(embed=embed)
                game['message_id'] = msg.id
        else:
            msg = await ctx.send(embed=embed)
            game['message_id'] = msg.id

    async def _pick_next_story_turn(self, ctx):
        game = self.story_games.get(ctx.channel.id)
        if not game:
            return None

        last_author_id = game['sentences'][-1][0]
        
        potential_player_ids = [pid for pid in game['participants'] if pid != last_author_id]

        if not potential_player_ids:
            # Everyone has had a turn, reset the pool (but still exclude last author)
            potential_player_ids = game['participants']
            if last_author_id in potential_player_ids and len(potential_player_ids) > 1:
                 potential_player_ids.remove(last_author_id)

        if not potential_player_ids:
            await self._end_story(ctx, "Not enough active players to continue.")
            return None

        next_user_id = random.choice(potential_player_ids)
        game['turn_user_id'] = next_user_id
        game['turn_started_at'] = datetime.utcnow()
        
        try:
            return await self.bot.fetch_user(next_user_id)
        except discord.NotFound:
            # If user not found, try to pick another
            return await self._pick_next_story_turn(ctx)

    async def _end_story(self, ctx, reason: str = None):
        game = self.story_games.get(ctx.channel.id)
        if not game:
            return

        story_text = ""
        for i, (author_id, author_name, sentence) in enumerate(game['sentences']):
            story_text += f"**{author_name}:** {sentence}\n"
        
        title = "📖 Story Complete!"
        description = story_text
        if reason:
            title = "📖 Story Ended"
            description = f"The story was ended early: {reason}\n\n---\n\n{story_text}"

        embed = discord.Embed(title=title, description=description, color=discord.Color.dark_green())
        await ctx.send(embed=embed)

        if game.get('message_id'):
            try:
                msg = await ctx.channel.fetch_message(game['message_id'])
                await msg.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
        
        if ctx.channel.id in self.story_games:
            del self.story_games[ctx.channel.id]

    @commands.group(name="story", invoke_without_command=True)
    async def story(self, ctx):
        """A collaborative storytelling game. Use `?story help` for commands."""
        game = self.story_games.get(ctx.channel.id)
        if game:
            await self._update_story_message(ctx)
        else:
            embed = discord.Embed(title="✍️ Story Game Help", color=discord.Color.dark_green())
            embed.add_field(name="`?story start <first sentence>`", value="Starts a new story with a player sign-up.", inline=False)
            embed.add_field(name="`?story add <sentence>`", value="Adds the next sentence when it's your turn.", inline=False)
            embed.add_field(name="`?story take`", value="Steals the turn if the current user is AFK (5 min).", inline=False)
            embed.add_field(name="`?story stop`", value="Stops the current story (creator or admin only).", inline=False)
            await ctx.send(embed=embed)

    @story.command(name="start")
    async def story_start(self, ctx, *, first_sentence: str):
        """Starts a new collaborative story with a sign-up period."""
        if ctx.channel.id in self.story_games:
            await ctx.send("A story is already in progress in this channel. Use `?story stop` to end it first.")
            return

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        signup_duration = 30

        embed = discord.Embed(
            title="✍️ A New Story is Starting!",
            description=f"{ctx.author.mention} started a story. React with ✅ in the next {signup_duration} seconds to join!",
            color=discord.Color.dark_green()
        )
        embed.add_field(name="First Sentence", value=f'''{first_sentence}''')
        
        signup_message = await ctx.send(embed=embed)
        await signup_message.add_reaction("✅")

        await asyncio.sleep(signup_duration)

        try:
            updated_message = await ctx.channel.fetch_message(signup_message.id)
        except discord.NotFound:
            await ctx.send("The sign-up message was deleted. Aborting story.")
            return

        reaction = discord.utils.get(updated_message.reactions, emoji="✅")
        participants = [user async for user in reaction.users() if not user.bot]

        if ctx.author not in participants:
            participants.append(ctx.author)

        if len(participants) < 2:
            await signup_message.edit(
                content="Not enough players joined. The story has been cancelled.",
                embed=None
            )
            return

        await signup_message.delete()

        self.story_games[ctx.channel.id] = {
            'sentences': [(ctx.author.id, ctx.author.display_name, first_sentence)],
            'limit': 15,
            'participants': [p.id for p in participants],
            'turn_user_id': None,
            'message_id': None,
            'turn_started_at': None,
            'creator_id': ctx.author.id
        }

        next_user = await self._pick_next_story_turn(ctx)
        if next_user:
            await ctx.send(f"The story begins with {len(participants)} players! It's {next_user.mention}'s turn.")
            await self._update_story_message(ctx)

    @story.command(name="add")
    async def story_add(self, ctx, *, sentence: str):
        """Adds a sentence to the story."""
        game = self.story_games.get(ctx.channel.id)
        if not game:
            await ctx.send("There's no story running. Start one with `?story start`.", delete_after=10)
            return

        if ctx.author.id != game.get('turn_user_id'):
            await ctx.send("It's not your turn!", delete_after=10)
            return

        game['sentences'].append((ctx.author.id, ctx.author.display_name, sentence))
        
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        if len(game['sentences']) >= game['limit']:
            await self._end_story(ctx)
        else:
            next_user = await self._pick_next_story_turn(ctx)
            if next_user:
                await self._update_story_message(ctx)

    @story.command(name="take")
    async def story_take(self, ctx):
        """Takes the turn from an inactive player."""
        game = self.story_games.get(ctx.channel.id)
        if not game or not game.get('turn_user_id'):
            return

        if ctx.author.id == game.get('turn_user_id'):
            await ctx.send("It's already your turn!", delete_after=10)
            return

        time_since_turn = datetime.utcnow() - game['turn_started_at']
        if time_since_turn < timedelta(minutes=5):
            remaining = 300 - time_since_turn.total_seconds()
            await ctx.send(f"Please wait {int(remaining)} more seconds before taking the turn.", delete_after=10)
            return

        original_user_id = game['turn_user_id']
        game['turn_user_id'] = ctx.author.id
        game['turn_started_at'] = datetime.utcnow()
        
        try:
            original_user = await self.bot.fetch_user(original_user_id)
            await ctx.send(f"{ctx.author.mention} has taken the turn from {original_user.display_name}!")
        except discord.NotFound:
            await ctx.send(f"{ctx.author.mention} has taken the turn!")
            
        await self._update_story_message(ctx)

    @story.command(name="stop")
    async def story_stop(self, ctx):
        """Stops the current story."""
        game = self.story_games.get(ctx.channel.id)
        if not game:
            await ctx.send("There is no story to stop in this channel.")
            return
        
        is_creator = ctx.author.id == game.get('creator_id')
        has_perms = ctx.author.guild_permissions.manage_guild

        if not is_creator and not has_perms:
            await ctx.send("You don't have permission to stop this story.")
            return

        await self._end_story(ctx, f"Stopped by {ctx.author.display_name}.")


async def setup(bot):
    await bot.add_cog(Games(bot))