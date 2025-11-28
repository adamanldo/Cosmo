import asyncio
import hashlib
import logging
import typing
from io import BytesIO
from typing import NamedTuple

import discord
from discord.ext import commands
from diskcache import Cache
from PIL import Image

from .utils.fmi_builder import FmiBuilder
from .utils.fmi_text import FmiText

log = logging.getLogger(__name__)

ALBUM_CACHE_DIR = "./.album_cache"
ALBUM_CACHE_SIZE = 2 * 1024**3
album_cache = Cache(ALBUM_CACHE_DIR, size_limit=ALBUM_CACHE_SIZE)

MBID_CACHE_DIR = "./.mbid_cache"
MBID_CACHE_SIZE = 1 * 1024**3
mbid_cache = Cache(MBID_CACHE_DIR, size_limit=MBID_CACHE_SIZE)

CAA_BASE = "https://coverartarchive.org/release"
MUSICBRAINZ_SEARCH_URL = "https://musicbrainz.org/ws/2/release/"


class LastFmParameters(NamedTuple):
    """Represents data returned from Last.fm"""

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
        key = hashlib.md5(f"{artist}:{album}".encode()).hexdigest()
        cached_image = album_cache.get(key)
        if cached_image:
            return BytesIO(cached_image)

        mbid = await self._get_mbid(artist, album)
        if mbid:
            img = await self._fetch_caa_art(mbid)
            if img:
                album_cache.set(key, img.getvalue())
                return img

        if lastfm_url:
            img = await self._fetch_lastfm_art(lastfm_url)
            if img:
                album_cache.set(key, img.getvalue())
                return img

        return None

    async def _get_mbid(self, artist, album):
        key = f"{artist}:{album}"
        cached_mbid = mbid_cache.get(key)
        if cached_mbid:
            return cached_mbid

        query = f'artist:"{artist}" AND release:"{album}"'
        params = {"query": query, "fmt": "json", "limit": 1}
        headers = {"User-Agent": self.bot.user_agent}

        try:
            async with self.bot.session.get(
                MUSICBRAINZ_SEARCH_URL, params=params, headers=headers
            ) as resp:
                if resp.status == 200:
                    js = await resp.json()
                    releases = js.get("releases")
                    if releases:
                        mbid = releases[0]["id"]
                        mbid_cache.set(key, mbid)
                        return mbid
        except Exception as e:
            log.warning("MusicBrainz request failed for %s/%s: %s", artist, album, e)

        return None

    async def _fetch_caa_art(self, mbid):
        url = f"{CAA_BASE}/{mbid}/front-250"
        try:
            async with self.bot.session.get(url) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    return BytesIO(content)
                elif resp.status == 404:
                    log.warning("No CAA art found for MBID %s", mbid)
                    return None
                else:
                    log.warning(
                        "CAA returned unexpected status %d for MBID %s",
                        resp.status,
                        mbid,
                    )
        except Exception:
            log.exception("CAA request failed for MBID %s", mbid)
        return None

    async def _fetch_lastfm_art(self, lastfm_url):
        try:
            async with self.bot.session.get(lastfm_url) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    return BytesIO(content)
                elif resp.status == 404:
                    log.warning("No Last.fm art found at url: %s", lastfm_url)
                    return None
                else:
                    log.warning(
                        "Last.fm returned unexpected status %d for url: %s",
                        resp.status,
                        lastfm_url,
                    )
        except Exception:
            log.exception("Last.fm request failed for url %s", lastfm_url)
        return None

    async def _fetch_avatar(self, url):
        try:
            async with self.bot.session.get(url) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    return BytesIO(content)
                else:
                    log.warning(
                        "Failed to fetch avatar: %s returned %d", url, resp.status
                    )
                    return None
        except Exception:
            log.exception("Exception in fetching avatar: %s", url)
            return None

    async def _generate_fmi(self, lastfmdata, avatar_url):
        album_task = self._get_album_art(
            artist=lastfmdata.artist,
            album=lastfmdata.album,
            lastfm_url=lastfmdata.albumartlink,
        )

        avatar_task = self._fetch_avatar(avatar_url)

        album_result, avatar_result = await asyncio.gather(album_task, avatar_task)

        album_bytes = album_result
        if album_bytes is None:
            log.error(
                "Album art not found for %s / %s", lastfmdata.artist, lastfmdata.album
            )
            raise AlbumArtError()

        avatar_bytes = avatar_result
        if avatar_bytes is None:
            raise AvatarNotFoundError()

        try:
            album_bytes.seek(0)
            header = album_bytes.read(6)
            album_bytes.seek(0)
            if header in (b"GIF87a", b"GIF89a"):
                album_bytes = self._gif_to_png(album_bytes)
        except Exception:
            log.exception("Failed to convert GIF to PNG")
            raise AlbumArtError()

        text = FmiText(lastfmdata)
        image = FmiBuilder(album_bytes, avatar_bytes, text).create_fmi()

        return image

    def _gif_to_png(self, gif):
        gif = Image.open(gif)
        output = BytesIO()
        gif.save(output, format="PNG")
        output.seek(0)
        return output


async def setup(bot):
    await bot.add_cog(Fmi(bot))
