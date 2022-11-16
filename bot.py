import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import aiohttp
import logging

log = logging.getLogger()

#load environmental variables
load_dotenv()

class Cosmo(commands.Bot):
    def __init__(self):

        self.api_key = os.getenv("API_KEY")
        self.user_agent = "Cosmo"

        intents = discord.Intents(members=True, messages=True, guilds=True, message_content=True)

        super().__init__(intents=intents, command_prefix='?')
        super().remove_command('help')

    async def on_command_error(self, ctx, error):
        ignored = (commands.CommandNotFound, commands.UserInputError)
        if isinstance(error, ignored):
            return

        log.error(error)
        raise error

    async def close(self):
        await super().close()
