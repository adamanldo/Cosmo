import os

from dotenv import load_dotenv

load_dotenv()

BOT_DEBUG = int(os.getenv("BOT_DEBUG"))
BOT_PREFIX = os.getenv("BOT_PREFIX")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
USER_AGENT = os.getenv("USER_AGENT")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
