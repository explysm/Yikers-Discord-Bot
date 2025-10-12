import discord
from discord.ext import commands
import aiohttp
import logging
import json
import os
import uuid
import re
from datetime import datetime
from tmdbv3api import TMDb, Movie
import html

class Utility(commands.Cog):
    """Utility commands for dictionary, lookups, surveys, and more."""

    def __init__(self, bot):
        self.bot = bot
        self.dictionary_api_url = "https://api.dictionaryapi.dev/api/v2/entries/en/"
        self.wikipedia_api_url = "https://en.wikipedia.org/w/api.php"
        self.github_api_url = "https://api.github.com/repos/"
        self.tvmaze_api_url = "https://api.tvmaze.com/singlesearch/shows"
        self.surveys_file = "servers/surveys.json"
        self.surveys = self._load_surveys()

        if hasattr(bot, 'tmdb_api_key') and bot.tmdb_api_key and bot.tmdb_api_key != 'YOUR_TMDB_API_KEY':
            self.tmdb = TMDb()
            self.tmdb.api_key = bot.tmdb_api_key
        else:
            self.tmdb = None

    def _load_surveys(self):
        """Loads survey data from the JSON file."""
        if os.path.exists(self.surveys_file):
            with open(self.surveys_file, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    logging.warning(f"Surveys file '{self.surveys_file}' is empty or malformed.")
                    return {}
        return {}

    def _save_surveys(self):
        """Saves current survey data to the JSON file."""
        os.makedirs(os.path.dirname(self.surveys_file), exist_ok=True)
        with open(self.surveys_file, 'w') as f:
            json.dump(self.surveys, f, indent=4)

    async def fetch_json(self, url, params=None):
        """Helper to fetch JSON from a given URL."""
        headers = {
            'User-Agent': 'YikersDiscordBot/1.0 (https://github.com/YikeGames-P/yikers-discord-bot)'
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 404:
                        return None # Gracefully handle Not Found
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                logging.error(f"API request failed for {url}: {e}")
                return None
            except Exception as e:
                logging.error(f"An unexpected error occurred during API fetch for {url}: {e}")
                return None

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listener for custom commands."""
        if message.author.bot or not message.guild:
            return

        # Prevent custom commands from firing if a real command is being used
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        guild_id = str(message.guild.id)
        custom_commands = self.bot.settings.get(guild_id, {}).get('custom_commands', {})
        
        trigger = message.content
        if trigger in custom_commands:
            await message.channel.send(custom_commands[trigger])

    @commands.command(name="define", aliases=["def"])
    async def define_word(self, ctx, *, word: str):
        """Gets the definition of a word."""
        async with ctx.typing():
            data = await self.fetch_json(f"{self.dictionary_api_url}{word}")

            if not data or not isinstance(data, list):
                await ctx.send(f"Sorry, I couldn't find a definition for **{word}**.")
                return

            embed = discord.Embed(
                title=f"📖 Definition of {data[0]['word']}",
                color=discord.Color.green()
            )

            if 'phonetic' in data[0] and data[0]['phonetic']:
                 embed.description = f"*{data[0]['phonetic']}*"
            
            for meaning in data[0]['meanings']:
                definitions = []
                for definition in meaning['definitions']:
                    def_text = f"• {definition['definition']}"
                    if 'example' in definition and definition['example']:
                        def_text += f"\n  *Example: \"{definition['example']}\"*"
                    definitions.append(def_text)
                
                if definitions:
                    current_value = ""
                    part_of_speech = f"**{meaning['partOfSpeech']}**"
                    field_count = 0
                    for i, definition_text in enumerate(definitions):
                        if len(current_value) + len(definition_text) + 2 > 1024:
                            field_name = part_of_speech if field_count == 0 else f"{part_of_speech} (cont.)"
                            embed.add_field(name=field_name, value=current_value, inline=False)
                            current_value = ""
                            field_count += 1
                        
                        current_value += definition_text + "\n"

                    if current_value:
                        field_name = part_of_speech if field_count == 0 else f"{part_of_speech} (cont.)"
                        embed.add_field(name=field_name, value=current_value, inline=False)

            if 'sourceUrls' in data[0] and data[0]['sourceUrls']:
                embed.set_footer(text=f"Source: {data[0]['sourceUrls'][0]}")

        await ctx.send(embed=embed)

    @commands.command(name="synonym", aliases=["syn"])
    async def get_synonyms(self, ctx, *, word: str):
        """Gets synonyms for a word."""
        async with ctx.typing():
            data = await self.fetch_json(f"{self.dictionary_api_url}{word}")

            if not data or not isinstance(data, list):
                await ctx.send(f"Sorry, I couldn't find **{word}**.")
                return

            synonyms = set()
            for meaning in data[0]['meanings']:
                for s in meaning.get('synonyms', []):
                    synonyms.add(s)

            if not synonyms:
                await ctx.send(f"No synonyms found for **{word}**.")
                return

            description = ", ".join(sorted(list(synonyms)))
            if len(description) > 4096:
                description = description[:4093] + "..."

            embed = discord.Embed(
                title=f"Synonyms for {data[0]['word']}",
                description=description,
                color=discord.Color.gold()
            )
        await ctx.send(embed=embed)

    @commands.command(name="wiki", aliases=["wikipedia"])
    async def wikipedia_search(self, ctx, *, query: str):
        """Searches Wikipedia for a topic and returns a summary."""
        async with ctx.typing():
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "srlimit": 1
            }
            search_data = await self.fetch_json(self.wikipedia_api_url, params=params)

            if not search_data or not search_data.get('query') or not search_data['query'].get('search'):
                await ctx.send(f"Sorry, I couldn't find anything on Wikipedia for **{query}**.")
                return

            page_title = search_data['query']['search'][0]['title']

            params = {
                "action": "query",
                "format": "json",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "titles": page_title,
                "redirects": 1,
            }
            page_data = await self.fetch_json(self.wikipedia_api_url, params=params)

            if not page_data or not page_data.get('query') or not page_data['query'].get('pages'):
                await ctx.send(f"Sorry, I couldn't retrieve the details for **{page_title}**.")
                return
            
            page_id = list(page_data['query']['pages'].keys())[0]
            extract = page_data['query']['pages'][page_id].get('extract', 'No summary available.')
            page_url = f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"

            if len(extract) > 4096:
                extract = extract[:4093] + "..."

            embed = discord.Embed(
                title=f"🌐 {page_title}",
                url=page_url,
                description=extract,
                color=discord.Color.light_grey()
            )
            embed.set_footer(text="Powered by Wikipedia")

        await ctx.send(embed=embed)

    @commands.group(name="survey", invoke_without_command=True)
    async def survey_group(self, ctx):
        """Lists active surveys or shows survey help."""
        guild_id = str(ctx.guild.id)
        active_surveys = []
        if guild_id in self.surveys:
            for survey_id, survey_data in self.surveys[guild_id].items():
                if survey_data.get('active', False):
                    active_surveys.append(f"`{survey_id}`: {survey_data['question']}")

        if not active_surveys:
            await ctx.send("There are no active surveys in this server. Use `?survey create <question>` to start one.")
            return

        embed = discord.Embed(
            title="Active Surveys",
            description="\n".join(active_surveys),
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    @survey_group.command(name="create")
    async def create_survey(self, ctx, *, question: str):
        """Creates a new survey."""
        guild_id = str(ctx.guild.id)
        survey_id = str(uuid.uuid4())[:8] # Short, unique ID

        if guild_id not in self.surveys:
            self.surveys[guild_id] = {}

        self.surveys[guild_id][survey_id] = {
            "question": question,
            "owner_id": ctx.author.id,
            "active": True,
            "responses": {},
            "message_id": None # To be filled after sending message
        }

        embed = discord.Embed(
            title="📊 New Survey Created!",
            description=f"**Question:** {question}\n\nUse `?survey respond {survey_id} <your_answer>` to participate.",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Survey ID: {survey_id}")
        
        msg = await ctx.send(embed=embed)
        self.surveys[guild_id][survey_id]["message_id"] = msg.id
        self._save_surveys()

    @survey_group.command(name="respond")
    async def respond_survey(self, ctx, survey_id: str, *, answer: str):
        """Responds to an active survey."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        if guild_id not in self.surveys or survey_id not in self.surveys[guild_id]:
            await ctx.send("Invalid survey ID.")
            return

        survey = self.surveys[guild_id][survey_id]
        if not survey.get('active', False):
            await ctx.send("This survey is no longer active.")
            return

        survey["responses"][user_id] = answer
        self._save_surveys()
        await ctx.message.add_reaction("✅")

    @survey_group.command(name="view")
    async def view_survey(self, ctx, survey_id: str):
        """Views the question and responses of a survey."""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.surveys or survey_id not in self.surveys[guild_id]:
            await ctx.send("Invalid survey ID.")
            return

        survey = self.surveys[guild_id][survey_id]
        question = survey["question"]
        responses = survey["responses"]

        embed = discord.Embed(
            title=f"Survey Results: {question}",
            color=discord.Color.blurple()
        )

        if not responses:
            embed.description = "No responses yet."
        else:
            # Count responses
            response_counts = {}
            for response in responses.values():
                response_counts[response] = response_counts.get(response, 0) + 1
            
            description = ""
            for response, count in sorted(response_counts.items(), key=lambda item: item[1], reverse=True):
                description += f"**{response}**: {count} vote(s)\n"
            embed.description = description

        await ctx.send(embed=embed)

    @survey_group.command(name="end")
    @commands.has_permissions(manage_guild=True)
    async def end_survey(self, ctx, survey_id: str):
        """Ends an active survey."""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.surveys or survey_id not in self.surveys[guild_id]:
            await ctx.send("Invalid survey ID.")
            return

        survey = self.surveys[guild_id][survey_id]
        if not survey.get('active', False):
            await ctx.send("This survey is already inactive.")
            return
        
        if ctx.author.id != survey["owner_id"] and not ctx.author.guild_permissions.manage_guild:
             await ctx.send("You must be the survey creator or have Manage Server permissions to end this survey.")
             return

        survey["active"] = False
        self._save_surveys()

        await ctx.send(f"Survey `{survey_id}` has been closed. Use `?survey view {survey_id}` to see the final results.")

    # --- Custom Commands Feature ---
    @commands.group(name="customcmd", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def customcmd(self, ctx):
        """Base command for managing custom commands."""
        await ctx.send("Invalid subcommand. Use `add`, `delete`, or `list`.")

    @customcmd.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def cc_add(self, ctx, name: str, *, response: str):
        """Adds or updates a custom command for this server."""
        guild_id = str(ctx.guild.id)
        if 'custom_commands' not in self.bot.settings[guild_id]:
            self.bot.settings[guild_id]['custom_commands'] = {}
        
        self.bot.settings[guild_id]['custom_commands'][name] = response
        self.bot.save_settings()
        await ctx.send(f"Custom command `{name}` has been saved.")

    @customcmd.command(name="delete")
    @commands.has_permissions(manage_guild=True)
    async def cc_delete(self, ctx, name: str):
        """Deletes a custom command."""
        guild_id = str(ctx.guild.id)
        if 'custom_commands' in self.bot.settings[guild_id] and name in self.bot.settings[guild_id]['custom_commands']:
            del self.bot.settings[guild_id]['custom_commands'][name]
            self.bot.save_settings()
            await ctx.send(f"Custom command `{name}` has been deleted.")
        else:
            await ctx.send(f"Custom command `{name}` not found.")

    @customcmd.command(name="list")
    async def cc_list(self, ctx):
        """Lists all custom commands for this server."""
        guild_id = str(ctx.guild.id)
        cmds = self.bot.settings.get(guild_id, {}).get('custom_commands', {})
        if not cmds:
            await ctx.send("This server has no custom commands.")
            return
        
        embed = discord.Embed(title="Custom Commands", color=discord.Color.teal())
        description = "\n".join([f"`{name}`" for name in cmds.keys()])
        embed.description = description
        await ctx.send(embed=embed)

    # --- GitHub Stats Feature ---
    @commands.command(name="github", aliases=["gh"])
    async def github_stats(self, ctx, *, repo_path: str):
        """
        Fetches statistics for a public GitHub repository.
        Usage: ?github <username/repository>
        Example: ?github explysm/yikers-discord-bot
        """
        if '/' not in repo_path:
            owner = 'explysm'
            repo = repo_path
        else:
            parts = repo_path.split('/')
            if len(parts) != 2 or not all(parts):
                await ctx.send("Invalid format. Please use `username/repository`.")
                return
            owner, repo = parts

        url = f"{self.github_api_url}{owner}/{repo}"
        
        async with ctx.typing():
            data = await self.fetch_json(url)

            if not data:
                await ctx.send("Sorry, I couldn't find that repository.")
                return

            embed = discord.Embed(
                title=f"📂 {data.get('full_name')}",
                url=data.get('html_url'),
                description=data.get('description', 'No description provided.'),
                color=discord.Color.from_rgb(120, 120, 120)
            )
            
            if data.get('owner', {}).get('avatar_url'):
                embed.set_thumbnail(url=data['owner']['avatar_url'])
            
            embed.add_field(name="Language", value=data.get('language', 'N/A'), inline=True)
            embed.add_field(name="Stars", value=f"⭐ {data.get('stargazers_count', 0)}", inline=True)
            embed.add_field(name="Forks", value=f"🍴 {data.get('forks_count', 0)}", inline=True)
            embed.add_field(name="Watching", value=f"👀 {data.get('subscribers_count', 0)}", inline=True)
            embed.add_field(name="Open Issues", value=data.get('open_issues_count', 0), inline=True)
            
            try:
                created_at = datetime.strptime(data['created_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%b %d, %Y")
                pushed_at = datetime.strptime(data['pushed_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%b %d, %Y")
                embed.add_field(name="Created", value=created_at, inline=False)
                embed.add_field(name="Last Push", value=pushed_at, inline=True)
            except (ValueError, KeyError):
                pass # Skip dates if they are missing or malformed

            await ctx.send(embed=embed)

    @commands.command(name="tv")
    async def tv_show_search(self, ctx, *, query: str):
        """Searches for a TV show and displays its information."""
        async with ctx.typing():
            params = {"q": query}
            data = await self.fetch_json(self.tvmaze_api_url, params=params)

            if not data:
                await ctx.send(f"Sorry, I couldn't find a TV show named '{query}'.")
                return

            embed = discord.Embed(
                title=data.get('name', 'N/A'),
                url=data.get('url'),
                description=html.unescape(re.sub('<[^<]+?>', '', data.get('summary', 'No summary available.'))),
                color=discord.Color.blue()
            )

            if data.get('image') and data['image'].get('medium'):
                embed.set_thumbnail(url=data['image']['medium'])

            embed.add_field(name="Language", value=data.get('language', 'N/A'), inline=True)
            embed.add_field(name="Status", value=data.get('status', 'N/A'), inline=True)
            if data.get('rating') and data['rating'].get('average'):
                embed.add_field(name="Rating", value=f"⭐ {data['rating']['average']}", inline=True)
            
            if data.get('genres'):
                embed.add_field(name="Genres", value=", ".join(data['genres']), inline=False)

            if data.get('schedule') and data['schedule']['days'] and data['schedule']['time']:
                schedule = f"{', '.join(data['schedule']['days'])} at {data['schedule']['time']}"
                embed.add_field(name="Schedule", value=schedule, inline=True)
            
            if data.get('network'):
                embed.add_field(name="Network", value=data['network']['name'], inline=True)

            embed.set_footer(text="Powered by TVmaze")
            await ctx.send(embed=embed)

    @commands.command(name="movie")
    async def movie_search(self, ctx, *, query: str):
        """Searches for a movie and displays its information."""
        if not self.tmdb:
            await ctx.send("The movie command is not configured. Please set the `api_key` in the `[tmdb]` section of `bot-settings.ini`.")
            return

        async with ctx.typing():
            movie = Movie()
            search_results = movie.search(query)

            if not search_results:
                await ctx.send(f"Sorry, I couldn't find a movie named '{query}'.")
                return
            
            # Get details of the first result
            movie_details = movie.details(search_results[0].id)

            embed = discord.Embed(
                title=movie_details.title,
                url=f"https://www.themoviedb.org/movie/{movie_details.id}",
                description=movie_details.overview,
                color=discord.Color.red()
            )

            if movie_details.poster_path:
                embed.set_thumbnail(url=f"https://image.tmdb.org/t/p/w500{movie_details.poster_path}")

            embed.add_field(name="Release Date", value=movie_details.release_date, inline=True)
            embed.add_field(name="Rating", value=f"⭐ {movie_details.vote_average:.1f}/10", inline=True)
            embed.add_field(name="Runtime", value=f"{movie_details.runtime} min", inline=True)

            if movie_details.genres:
                genres = [genre['name'] for genre in movie_details.genres]
                embed.add_field(name="Genres", value=", ".join(genres), inline=False)

            embed.set_footer(text="Powered by The Movie Database (TMDb)")
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Utility(bot))