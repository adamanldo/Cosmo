from bot import Cosmo 
import logging
from logging import handlers
from cogs.db import create_pool
import asyncio

def main():

    #set up logging
    max_bytes = 32 * 1024 * 1024
    log = logging.getLogger()
    log.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(filename='cosmo.log', encoding='utf-8', mode='w', maxBytes = max_bytes, backupCount=5)
    date_format = '%Y-%m-%d %H:%M:%S'
    format = logging.Formatter('[{asctime}] {name}: {message}', date_format, style='{')
    handler.setFormatter(format)
    log.addHandler(handler)

    #set up postgres connection pool
    loop = asyncio.get_event_loop()
    try:
        pool = loop.run_until_complete(create_pool())
    except Exception as e:
        print(f"Could not connect to PostgreSQL. Exiting...")
        print(f"Exception: {e}")
        return

    bot = Cosmo()
    bot.pool = pool
    bot.run()

if __name__ == '__main__':
    main()
