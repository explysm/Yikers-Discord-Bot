import discord
from discord.ext import commands
import logging
import aiohttp
import typing

class AI(commands.Cog):
    """AI-powered commands, such as text summarization."""
    def __init__(self, bot):
        self.bot = bot
        self.summary_api_url = "https://api-inference.huggingface.co/models/sshleifer/distilbart-cnn-12-6"
 
    async def query_api(self, payload, url):
        headers = {"Authorization": f"Bearer {self.bot.hf_token}"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logging.error(f"Hugging Face API Error: {response.status} - {await response.text()}")
                    return None

    async def query_summary_api(self, text):
        payload = {
            "inputs": text,
            "parameters": {
                "min_length": 30,
                "max_length": 150,
                "do_sample": False
            }
        }
        summary_text = None
        response_data = await self.query_api(payload, self.summary_api_url)
        if response_data and isinstance(response_data, list) and response_data[0].get('summary_text'):
            summary_text = response_data[0]['summary_text']
        return summary_text

    @commands.command()
    async def summary(self, ctx, limit: typing.Optional[int] = 50):
        """Summarizes recent messages in the channel using AI.

        Usage: ?summary [number_of_messages]
        Example: ?summary 100
        """
        if not self.bot.hf_token or "YOUR_TOKEN_HERE" in self.bot.hf_token:
            await ctx.send("The AI features are enabled, but the Hugging Face token is not configured in `bot-settings.ini`.")
            return

        if limit <= 0 or limit > 200:
            await ctx.send("Please provide a number of messages between 1 and 200.")
            return

        status_msg = await ctx.send(f"🤖 Reading the last {limit} messages and thinking...")

        messages = []
        async for message in ctx.channel.history(limit=limit):
            if not message.author.bot and message.content:
                messages.append(f"{message.author.display_name}: {message.content}")
        
        if not messages:
            await status_msg.edit(content="No recent messages found to summarize.")
            return

        # The API works best with newest messages last
        messages.reverse()
        full_text = "\n".join(messages)

        # The API has a limit on input text length, truncate if necessary
        max_input_length = 10000 # A safe character limit
        if len(full_text) > max_input_length:
            full_text = full_text[:max_input_length]
            await ctx.send("Warning: The conversation is very long. Summarizing the most recent part.", delete_after=10)

        summary_text = await self.query_summary_api(full_text)

        if summary_text:
            embed = discord.Embed(
                title=f"Summary of the Last {limit} Messages",
                description=summary_text,
                color=discord.Color.blue()
            )
            await status_msg.edit(content=None, embed=embed)
        else:
            await status_msg.edit(content="Sorry, I couldn't generate a summary at this time.")

async def setup(bot):
    await bot.add_cog(AI(bot))