from bot import Cosmo
import logging
from logging.handlers import RotatingFileHandler
import argparse
from cogs.db import create_pool
import asyncio
import os
from dotenv import load_dotenv
import aiohttp

load_dotenv()


async def main(console_output):
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

    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(format)
        console_handler.setLevel(logging.WARNING)
        log.addHandler(console_handler)

    bot = Cosmo()

    token = os.getenv("DISCORD_TOKEN")

    # add every cog in the top level cogs folder (ignore subdirectories, these are not cogs)
    cogs = []
    for c in os.listdir("./cogs"):
        if c.endswith(".py"):
            cogs.append("cogs." + c[:-3])

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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--console-output", help="Prints logs to the console", default=False
    )
    args = parser.parse_args()
    asyncio.run(main(args.console_output))
