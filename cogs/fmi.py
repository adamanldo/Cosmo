import asyncio
import logging
import os
import typing
from io import BytesIO
from typing import NamedTuple

import discord
import musicbrainzngs
from discord.ext import commands

from .utils.album_art import get_album_image
from .utils.album_art.cache import AlbumCache
from .utils.album_art.fetcher import fetch_avatar_bytes
from .utils.fmi_builder import FmiBuilder
from .utils.fmi_text import FmiText

log = logging.getLogger(__name__)

# base cosmo directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ALBUM_CACHE_DIR = os.path.join(BASE_DIR, ".album_cache")
ALBUM_CACHE_SIZE = 2 * 1024**3
album_cache = AlbumCache(ALBUM_CACHE_DIR, size_limit=ALBUM_CACHE_SIZE)


class LastFmParameters(NamedTuple):
    title: str
    artist: str
    album: str
    albumartlink: str


class LastFMInfoError(commands.CommandError):
    pass


class AlbumArtError(commands.CommandError):
    pass


class AvatarNotFoundError(commands.CommandError):
    pass


class NoScrobblesFoundError(commands.CommandError):
    pass


class UserNotFound(commands.CommandError):
    pass


class ScrobbleMissingInfoError(commands.CommandError):
    pass


class MentionedUserNotFound(commands.CommandError):
    def __init__(self, name, *args, **kwargs):
        self.name = name
        super().__init__(*args, **kwargs)


class Fmi(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.album_cache = album_cache

        musicbrainzngs.set_useragent(
            "Cosmo",
            "1.0",
        )

    async def find_user(self, discord_id):
        query = "SELECT username FROM discord WHERE id = $1;"
        async with self.bot.db_pool.acquire() as connection:
            row = await connection.fetchrow(query, discord_id)
            if row:
                return row.get("username")
            return None

    @commands.command(name="set")
    async def register(self, ctx, lastfm_username: str):
        query = """INSERT INTO discord (id, username)
                    VALUES ($1, $2)
                    ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username"""
        try:
            async with self.bot.db_pool.acquire() as connection:
                async with connection.transaction():
                    await connection.execute(
                        query, ctx.message.author.id, lastfm_username
                    )
                    await ctx.send(
                        "{}'s Last.fm account has been set.".format(
                            ctx.message.author.display_name
                        )
                    )
        except Exception:
            log.exception(
                "Failed to add/update last.fm username for user %s",
                ctx.message.author.id,
            )
            await ctx.send("There was an error adding the user.")

    @commands.command(name="fmi")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def fmi(self, ctx, other_user: typing.Optional[discord.Member] = None):
        if other_user:
            lastfm_username = await self.find_user(other_user.id)
            if lastfm_username is None:
                raise MentionedUserNotFound(other_user.display_name)
            avatar_url = str(other_user.avatar.replace(format="png", size=128))
        else:
            lastfm_username = await self.find_user(ctx.message.author.id)
            if lastfm_username is None:
                raise UserNotFound
            avatar_url = str(ctx.author.avatar.replace(format="png", size=128))

        last_fm_info = await self._get_lastfm_info(lastfm_username)
        image = await self._generate_fmi(last_fm_info, avatar_url)
        await ctx.send(file=discord.File(image, "fmi.png"))

    @fmi.error
    async def fmi_error(self, ctx, error):
        if isinstance(error, MentionedUserNotFound):
            await ctx.send(
                "It looks like {} hasn't connected their Last.fm account.".format(
                    error.name
                )
            )
        elif isinstance(error, UserNotFound):
            await ctx.send(
                "It looks like you haven't connected your Last.fm account.\nTry using `.set [last.fm username]`"
            )
        elif isinstance(error, LastFMInfoError):
            await ctx.send(
                "Account doesn't exist on Last.fm or we can't connect to the Last.fm API."
            )
        elif isinstance(error, ScrobbleMissingInfoError):
            await ctx.send(
                "Your most recent scrobble is missing an album name or album artwork."
            )
        elif isinstance(error, AvatarNotFoundError):
            await ctx.send(
                "Couldn't fetch the avatar image. Try again in a few minutes."
            )
        elif isinstance(error, AlbumArtError):
            await ctx.send(
                "We can't get that album artwork right now, try again in a few minutes."
            )
        elif isinstance(error, NoScrobblesFoundError):
            await ctx.send("No scrobbles found.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send("You're using that too much.")
        else:
            await ctx.send("Something went wrong...")
            log.error("Error: ", exc_info=error)

    async def _get_lastfm_info(self, lastfm_username):
        params = {
            "method": "user.getrecenttracks",
            "limit": 1,
            "user": lastfm_username,
            "api_key": self.bot.api_key,
            "format": "json",
        }
        headers = {"User-Agent": self.bot.user_agent}
        url = "https://ws.audioscrobbler.com/2.0/"

        try:
            async with self.bot.session.get(
                url, headers=headers, params=params
            ) as resp:
                if resp.status != 200:
                    raise LastFMInfoError
                js = await resp.json()
        except Exception:
            log.exception("Failed to contact Last.fm for user %s", lastfm_username)
            raise LastFMInfoError

        try:
            recent = js.get("recenttracks", {})
            tracks = recent.get("track")

            if not tracks:
                raise NoScrobblesFoundError

            track = tracks[0] if isinstance(tracks, list) else tracks

            title = track.get("name")
            artist = (track.get("artist") or {}).get("#text")
            album = (track.get("album") or {}).get("#text")

            images = track.get("image") or []
            albumartlink = ""
            if isinstance(images, list) and len(images) > 2:
                albumartlink = (images[2] or {}).get("#text", "")

            lastfmdata = LastFmParameters(
                title=title,
                artist=artist,
                album=album,
                albumartlink=albumartlink,
            )

            if not all(lastfmdata):
                raise ScrobbleMissingInfoError

            return lastfmdata
        except commands.CommandError:
            raise
        except Exception:
            log.exception(
                "Unexpected Last.fm JSON structure for user %s: %s", lastfm_username, js
            )
            raise LastFMInfoError

    async def _get_album_art(self, artist, album, lastfm_url):
        try:
            return await get_album_image(
                self.bot.session,
                self.album_cache,
                artist,
                album,
                lastfm_url,
            )
        except Exception as e:
            log.exception("Error getting album art for %s / %s: %s", artist, album, e)
            return None

    async def _fetch_avatar(self, avatar_url):
        try:
            avatar_bytes = await fetch_avatar_bytes(self.bot.session, avatar_url)
            if avatar_bytes:
                return BytesIO(avatar_bytes)
            return None
        except Exception as e:
            log.exception("Error fetching avatar: %s", e)
            return None

    async def _generate_fmi(self, lastfmdata, avatar_url):
        album_task = self._get_album_art(
            artist=lastfmdata.artist,
            album=lastfmdata.album,
            lastfm_url=lastfmdata.albumartlink,
        )

        avatar_task = self._fetch_avatar(avatar_url)

        album_result, avatar_result = await asyncio.gather(album_task, avatar_task)

        album_bytes_io = album_result
        if album_bytes_io is None:
            log.error(
                "Album art not found for %s / %s", lastfmdata.artist, lastfmdata.album
            )
            raise AlbumArtError()

        avatar_bytes = avatar_result
        if avatar_bytes is None:
            raise AvatarNotFoundError()

        text = FmiText(lastfmdata)
        image = FmiBuilder(album_bytes_io, avatar_bytes, text).create_fmi()

        return image


async def setup(bot):
    await bot.add_cog(Fmi(bot))
