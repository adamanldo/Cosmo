import aiohttp
import asyncpg
import discord
from discord.ext import commands
import logging
import config

log = logging.getLogger(__name__)


class Cosmo(commands.Bot):
    def __init__(self, cogs):
        self.api_key = config.LASTFM_API_KEY
        self.user_agent = config.USER_AGENT
        self.initial_cogs = cogs

        intents = discord.Intents(
            members=True, messages=True, guilds=True, message_content=True
        )

        super().__init__(intents=intents, command_prefix=config.BOT_PREFIX)
        super().remove_command("help")

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()

        try:
            self.db_pool = await asyncpg.create_pool(database="cosmo", user="postgres")
        except Exception as e:
            log.error(f"Failed to create db pool: {e}")
            raise e

        for cog in self.initial_cogs:
            try:
                await self.load_extension(cog)
            except Exception as e:
                log.error(f"Failed to load cog {cog}. Exception: {e}")
                raise e

    async def on_command_error(self, ctx, error):
        ignored = (commands.CommandNotFound, commands.UserInputError)
        if isinstance(error, ignored):
            return
        elif ctx.command.has_error_handler():
            return
        else:
            log.error("Error: ", exc_info=error)

    async def on_ready(self):
        print("Ready!")

    async def close(self):
        await self.session.close()
        await super().close()
