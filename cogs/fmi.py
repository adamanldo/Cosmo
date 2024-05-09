from PIL import Image
from io import BytesIO
from discord.ext import commands
import discord
from collections import namedtuple
import logging
from .utils.fmi_builder import FmiBuilder

log = logging.getLogger(__name__)


class LastFMInfoError(commands.CommandError):
    pass


class LastFMAlbumArtError(commands.CommandError):
    def __init__(self, resp, albumartlink, *args, **kwargs):
        self.resp = resp
        self.albumartlink = albumartlink
        super().__init__(*args, **kwargs)


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
        except Exception as e:
            log.error(e)
            await ctx.send("There was an error adding the user.")

    @commands.command(name="fmi")
    @commands.cooldown(3, 10, commands.BucketType.user)
    async def fmi(self, ctx, other_user: discord.Member = None):
        async with ctx.channel.typing():
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

            last_fm_info = await self.get_lastfm(lastfm_username)
            image = await self.generate_fmi(last_fm_info, avatar_url)
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
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Couldn't find that user in the server.")
        elif isinstance(error, LastFMInfoError):
            await ctx.send(
                "Account doesn't exist on Last.fm or we can't connect to the Last.fm API."
            )
        elif isinstance(error, ScrobbleMissingInfoError):
            await ctx.send(
                "Your most recent scrobble is missing an album name or album artwork."
            )
        elif isinstance(error, LastFMAlbumArtError):
            await ctx.send(
                "We can't get that album artwork from Last.fm right now, try again in a few minutes."
            )
            log.error(
                "Last.fm album art link response error: %s %s %s %s",
                error.resp,
                error.resp.history,
                error.resp.url,
                error.albumartlink,
            )
        elif isinstance(error, NoScrobblesFoundError):
            await ctx.send("No scrobbles found.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send("You're using that too much.")
        else:
            await ctx.send("Something went wrong...")
            log.error("Error: ", exc_info=error)

    # get currently playing last.fm info
    async def get_lastfm(self, lastfm_username):
        payload = {
            "method": "user.getrecenttracks",
            "limit": 1,
            "user": lastfm_username,
            "api_key": self.bot.api_key,
            "format": "json",
        }
        headers = {"user-agent": self.bot.user_agent}
        url = "https://ws.audioscrobbler.com/2.0/"

        LastFMParameters = namedtuple(
            "LastFMParameters", "title, artist, album, albumartlink"
        )

        async with self.bot.session.get(url, headers=headers, params=payload) as resp:
            if resp.status != 200:
                raise LastFMInfoError
            js = await resp.json()
            if js is None:
                raise NoScrobblesFoundError

            lastfmdata = LastFMParameters(
                title=js["recenttracks"]["track"][0]["name"],
                artist=js["recenttracks"]["track"][0]["artist"]["#text"],
                album=js["recenttracks"]["track"][0]["album"]["#text"],
                albumartlink=js["recenttracks"]["track"][0]["image"][2]["#text"],
            )

            if not all(lastfmdata):
                raise ScrobbleMissingInfoError

            return lastfmdata

    async def generate_fmi(self, lastfmdata, avatar_url):
        album_art_link = lastfmdata.albumartlink

        async with self.bot.session.get(avatar_url) as resp:
            avatar_bytes = BytesIO(await resp.read())

        async with self.bot.session.get(album_art_link) as resp:
            if resp.status != 200:
                raise LastFMAlbumArtError(resp, album_art_link)
            album_bytes = BytesIO(await resp.read())
        if album_art_link.endswith(".gif"):
            album_bytes = self.gif_to_png(album_bytes)

        image = FmiBuilder(album_bytes, avatar_bytes).create_fmi(lastfmdata)

        return image

    def gif_to_png(self, gif):
        gif = Image.open(gif)
        output = BytesIO()
        gif.save(output, format="PNG")
        return output


async def setup(bot):
    await bot.add_cog(Fmi(bot))
