import discord
from discord.ext import commands
import typing
import logging

class General(commands.Cog):
    """General purpose commands."""
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """Gets the bot's latency."""
        latency = self.bot.latency * 1000  # in ms
        embed = discord.Embed(title="Pong!", description=f"Latency: {latency:.2f}ms", color=discord.Color.blue())
        await ctx.send(embed=embed)

    @commands.command()
    async def userinfo(self, ctx, user: typing.Union[discord.Member, discord.User] = None):
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

    @commands.command(name="help")
    async def help(self, ctx, *, command_name: str = None):
        """Shows help for a command or a list of all commands."""
        prefix = self.bot.command_prefix(self.bot, ctx.message)

        if command_name is None:
            # General help embed
            embed = discord.Embed(title="Bot Commands", description=f"Use `{prefix}help <command>` for more info on a command.", color=discord.Color.blue())
            
            for cog_name in sorted(self.bot.cogs):
                cog = self.bot.get_cog(cog_name)
                cmds = [cmd for cmd in cog.get_commands() if not cmd.hidden]
                if not cmds:
                    continue
                
                command_list = [f"`{cmd.name}`" for cmd in sorted(cmds, key=lambda c: c.name)]
                embed.add_field(name=f"⚙️ {cog_name}", value=" ".join(command_list), inline=False)
                
            await ctx.send(embed=embed)

        else:
            # Specific command help
            command = self.bot.get_command(command_name)
            
            if command is None:
                await ctx.send(f"Command `{command_name}` not found.")
                return

            embed = discord.Embed(
                title=f"Help: `{prefix}{command.qualified_name}`",
                description=command.help or "No description provided.",
                color=discord.Color.green()
            )
            
            if command.aliases:
                embed.add_field(name="Aliases", value=", ".join([f"`{alias}`" for alias in command.aliases]), inline=False)

            # Construct usage string
            usage = f"`{prefix}{command.qualified_name}"
            if command.signature:
                usage += f" {command.signature}"
            usage += "`"
            embed.add_field(name="Usage", value=usage, inline=False)

            # If it's a group, list subcommands
            if isinstance(command, commands.Group):
                subcommands = [f"`{sub.name}` - {sub.short_doc or 'No description'}" for sub in sorted(command.commands, key=lambda c: c.name)]
                if subcommands:
                    embed.add_field(name="Subcommands", value="\n".join(subcommands), inline=False)

            await ctx.send(embed=embed)

    @commands.command()
    async def search(self, ctx, query: str, limit: typing.Optional[int] = 1000):
        """Searches recent messages in the channel for a query."""
        if limit <= 0:
            await ctx.send("The number of messages to search must be positive.")
            return
        if limit > 5000:
            await ctx.send("You can search a maximum of 5000 messages at a time.")
            return

        status_message = await ctx.send(f"🔍 Searching the last {limit} messages for \"{query}\"...")

        matches = []
        async for message in ctx.channel.history(limit=limit):
            if query.lower() in message.content.lower() and not message.author.bot:
                matches.append(message)
        
        if not matches:
            await status_message.edit(content=f"No results found for \"{query}\".")
            return

        max_results = 10
        results_to_display = matches[:max_results]
        results_to_display.reverse() # Show oldest results first

        embed = discord.Embed(
            title=f"Found {len(matches)} result(s) for \"{query}\"",
            color=discord.Color.blue()
        )

        description_lines = []
        for msg in results_to_display:
            clean_content = discord.utils.escape_markdown(msg.content)
            snippet = clean_content.replace('\n', ' ')[:80]
            if len(clean_content) > 80:
                snippet += '...'
            
            description_lines.append(f"[`Jump`]({msg.jump_url}) **{msg.author.name}**: {snippet}")
        
        embed.description = "\n".join(description_lines)
        embed.set_footer(text=f"Searched the last {limit} messages. Showing up to {min(len(matches), max_results)} results.")

        await status_message.edit(content=None, embed=embed)

    @commands.command()
    async def ctest(self, ctx, *, message: str = "This is a test log."):
        """Sends a message to the console to test logging."""
        logging.info(f"[CONSOLE TEST from {ctx.author.name}]: {message}")
        await ctx.send("Test message sent to console log.")

    @commands.command(name="spotify")
    async def spotify(self, ctx, user: discord.Member = None):
        """Shows what a user is listening to on Spotify. Defaults to you."""
        user = user or ctx.author
        
        spotify_activity = None
        for activity in user.activities:
            if isinstance(activity, discord.Spotify):
                spotify_activity = activity
                break

        if spotify_activity is None:
            await ctx.send(f"{user.name} is not listening to Spotify.")
            return

        embed = discord.Embed(
            title=f"{user.name}'s Spotify",
            color=spotify_activity.color
        )
        embed.set_thumbnail(url=spotify_activity.album_cover_url)
        embed.add_field(name="Track", value=f"[{spotify_activity.title}](https://open.spotify.com/track/{spotify_activity.track_id})", inline=False)
        embed.add_field(name="Artist(s)", value=", ".join(spotify_activity.artists), inline=False)
        embed.add_field(name="Album", value=spotify_activity.album, inline=True)
        
        duration = spotify_activity.duration
        embed.add_field(name="Duration", value=f"{duration.seconds // 60:02d}:{duration.seconds % 60:02d}", inline=True)

        await ctx.send(embed=embed)

async def setup(bot):
    bot.remove_command('help')
    await bot.add_cog(General(bot))
