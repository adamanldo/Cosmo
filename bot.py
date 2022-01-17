import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import aiohttp
import logging

log = logging.getLogger()

#load environmental variables
load_dotenv()

cogs = (
    'cogs.fmi',
    'cogs.countdown',
    'cogs.db',
    'cogs.owner'
)

class Cosmo(commands.Bot):
    def __init__(self):

        self.api_key = os.getenv("API_KEY")
        self.user_agent = "Cosmo"

        intents = discord.Intents(members=True, messages=True, guilds=True)

        super().__init__(intents=intents, command_prefix='.')

        self.session = aiohttp.ClientSession(loop=self.loop)

        for cog in cogs:
            try:
                self.load_extension(cog)
            except Exception as e:
                print(f'Failed to load cog {cog}. Exception: {e}')

    async def on_command_error(self, error):
        ignored = (commands.CommandNotFound, commands.UserInputError)
        if isinstance(error, ignored):
            return

        log.error(error)
        raise error

    async def close(self):
        await super().close()
        await self.session.close()

    def run(self):
        token = os.getenv("DISCORD_TOKEN")
        super().run(token, reconnect=True)
