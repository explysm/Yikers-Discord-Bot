import discord
from discord.ext import commands
import asyncio

class Admin(commands.Cog):
    """Commands for server administration."""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild_id = str(member.guild.id)
        guild_settings = self.bot.settings.get(guild_id, {})
        
        welcome_channel_id = guild_settings.get("welcome_channel_id")
        welcome_message = guild_settings.get("welcome_message")

        if welcome_channel_id and welcome_message:
            channel = member.guild.get_channel(welcome_channel_id)
            if channel:
                formatted_message = welcome_message.replace("<<user>>", member.mention)
                await channel.send(formatted_message)

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def setprefix(self, ctx, prefix: str):
        """Sets the bot's prefix for this server."""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return
        guild_id = str(ctx.guild.id)
        if guild_id not in self.bot.settings:
            self.bot.settings[guild_id] = {}
        self.bot.settings[guild_id]["prefix"] = prefix
        self.bot.save_settings()
        await ctx.send(f"Prefix for this server has been set to `{prefix}`")

    @setprefix.error
    async def setprefix_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to do that.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Please provide a prefix.")

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def welcome(self, ctx):
        """Welcome message management commands."""
        await ctx.send("Invalid welcome command. Use `?welcome set`, `?welcome channel`, or `?welcome test`.")

    @welcome.command()
    @commands.has_permissions(manage_guild=True)
    async def set(self, ctx):
        """Sets the welcome message for this server."""
        await ctx.send('''Please send the welcome message. (Tip: use "<<user>>" to mention the user)''')
        
        try:
            message = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=300.0)
        except asyncio.TimeoutError:
            await ctx.send("You took too long to respond.")
            return

        guild_id = str(ctx.guild.id)
        if guild_id not in self.bot.settings:
            self.bot.settings[guild_id] = {}
        self.bot.settings[guild_id]["welcome_message"] = message.content
        self.bot.save_settings()
        await ctx.send("Welcome message has been set.")

    @welcome.command()
    @commands.has_permissions(manage_guild=True)
    async def channel(self, ctx, channel: discord.TextChannel):
        """Sets the welcome channel for this server."""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.bot.settings:
            self.bot.settings[guild_id] = {}
        self.bot.settings[guild_id]["welcome_channel_id"] = channel.id
        self.bot.save_settings()
        await ctx.send(f"Welcome channel has been set to {channel.mention}")

    @welcome.command()
    @commands.has_permissions(manage_guild=True)
    async def test(self, ctx):
        """Tests the welcome message."""
        guild_id = str(ctx.guild.id)
        guild_settings = self.bot.settings.get(guild_id, {})
        
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

async def setup(bot):
    await bot.add_cog(Admin(bot))
