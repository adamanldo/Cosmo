import asyncpg
from bot import Cosmo
import logging
from logging.handlers import RotatingFileHandler
import asyncio
import os
import aiohttp
import config


async def main():

    setup_logging()
    bot = Cosmo()
    token = config.DISCORD_TOKEN

    # add every cog in the top level cogs folder (ignore subdirectories, these are not cogs)
    cogs = []
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            cogs.append("cogs." + filename[:-3])

    async with bot:
        async with aiohttp.ClientSession() as session:
            bot.session = session
            try:
                bot.db_pool = await asyncpg.create_pool(
                    database="cosmo", user="postgres"
                )
            except Exception as e:
                print(f"Failed to create db pool: {e}")

            for cog in cogs:
                try:
                    await bot.load_extension(cog)
                except Exception as e:
                    print(f"Failed to load cog {cog}. Exception: {e}")
            await bot.start(token)


def setup_logging():

    # set up logging
    max_bytes = 32 * 1024 * 1024
    log = logging.getLogger()
    log.setLevel(logging.INFO)

    file_handler = RotatingFileHandler(
        filename="cosmo.log",
        encoding="utf-8",
        mode="w",
        maxBytes=max_bytes,
        backupCount=5,
    )

    date_format = "%m-%d-%Y %I:%M:%S %p"
    format = logging.Formatter("[{asctime}] {name}: {message}", date_format, style="{")
    file_handler.setFormatter(format)
    file_handler.setLevel(logging.WARNING)
    log.addHandler(file_handler)

    if config.BOT_DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(format)
        console_handler.setLevel(logging.WARNING)
        log.addHandler(console_handler)


if __name__ == "__main__":
    asyncio.run(main())
