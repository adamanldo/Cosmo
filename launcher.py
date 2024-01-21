from bot import Cosmo
import logging
from logging import handlers
from cogs.db import create_pool
import asyncio
import os
from dotenv import load_dotenv
import aiohttp

load_dotenv()

cogs = ("cogs.fmi", "cogs.countdown", "cogs.db", "cogs.owner", "cogs.help")


async def main():
    # set up logging
    max_bytes = 32 * 1024 * 1024
    log = logging.getLogger()
    log.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(
        filename="cosmo.log",
        encoding="utf-8",
        mode="w",
        maxBytes=max_bytes,
        backupCount=5,
    )
    date_format = "%m-%d-%Y %I:%M:%S %p"
    format = logging.Formatter("[{asctime}] {name}: {message}", date_format, style="{")
    handler.setFormatter(format)
    log.addHandler(handler)

    bot = Cosmo()

    token = os.getenv("DISCORD_TOKEN")

    async with bot:
        async with aiohttp.ClientSession() as session:
            bot.session = session
            try:
                bot.pool = await create_pool()
            except Exception as e:
                print(f"Exception: {e}")

            for cog in cogs:
                try:
                    await bot.load_extension(cog)
                except Exception as e:
                    print(f"Failed to load cog {cog}. Exception: {e}")
            await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
