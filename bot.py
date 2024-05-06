import discord
from discord.ext import commands
import logging
import config

log = logging.getLogger(__name__)


class Cosmo(commands.Bot):
    def __init__(self):
        self.api_key = config.LASTFM_API_KEY
        self.user_agent = config.USER_AGENT

        intents = discord.Intents(
            members=True, messages=True, guilds=True, message_content=True
        )

        super().__init__(intents=intents, command_prefix=config.BOT_PREFIX)
        super().remove_command("help")

    async def on_command_error(self, ctx, error):
        ignored = (commands.CommandNotFound, commands.UserInputError)
        if isinstance(error, ignored):
            return
        elif ctx.command.has_error_handler():
            return
        else:
            log.error("Error: ", exc_info=error)

    async def close(self):
        await self.session.close()
        await super().close()
