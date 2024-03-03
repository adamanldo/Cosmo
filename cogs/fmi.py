from .utils.dominant_colors import dominant_colors
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import re
from discord.ext import commands
import discord
from collections import namedtuple
import logging

log = logging.getLogger(__name__)

BLACK = 0, 0, 0
WHITE = 255, 255, 255


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


class MentionedUserNotFound(commands.CommandError):
    def __init__(self, name, *args, **kwargs):
        self.name = name
        super().__init__(*args, **kwargs)


class Fmi(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="fmi")
    @commands.cooldown(3, 10, commands.BucketType.user)
    async def fmi(self, ctx, *args):
        db = self.bot.get_cog("DB")
        if ctx.message.mentions and len(ctx.message.mentions) == 1:
            lastfmusername = await db.find_user(ctx.message.mentions[0].id)
            if lastfmusername is None:
                raise MentionedUserNotFound(ctx.message.mentions[0].display_name)
            avatar = str(ctx.message.mentions[0].avatar.replace(format="png", size=128))
            image = await self.generate_fmi(
                await self.get_lastfm(lastfmusername), avatar
            )
            await ctx.send(file=discord.File(image, "fmi.png"))
        else:
            discordID = ctx.message.author.id
            lastfmusername = await db.find_user(discordID)
            if lastfmusername is None:
                raise UserNotFound
            avatar = str(ctx.author.avatar.replace(format="png", size=128))
            image = await self.generate_fmi(
                await self.get_lastfm(lastfmusername), avatar
            )
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
                "It looks like you haven't connected your Last.fm account.\nTry using `.set username`"
            )
        elif isinstance(error, LastFMInfoError):
            await ctx.send(
                "Account doesn't exist on Last.fm or we can't connect to the Last.fm API."
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
            log.error(error.original)

    # get currently playing last.fm info
    async def get_lastfm(self, lastfmusername):
        payload = {
            "method": "user.getrecenttracks",
            "user": lastfmusername,
            "api_key": self.bot.api_key,
            "format": "json",
        }
        headers = {"user-agent": self.bot.user_agent}
        url = "https://ws.audioscrobbler.com/2.0/"

        LastFMParameters = namedtuple(
            "LastFMParameters", "artist, album, albumartlink, title"
        )

        async with self.bot.session.get(url, headers=headers, params=payload) as resp:
            if resp.status != 200:
                raise LastFMInfoError
            js = await resp.json()
            if js is None:
                raise NoScrobblesFoundError

            lastfmdata = LastFMParameters(
                artist=js["recenttracks"]["track"][0]["artist"]["#text"],
                album=js["recenttracks"]["track"][0]["album"]["#text"],
                albumartlink=js["recenttracks"]["track"][0]["image"][2]["#text"],
                title=js["recenttracks"]["track"][0]["name"],
            )

            return lastfmdata

    async def generate_fmi(self, lastfmdata, avatar_url):
        async with self.bot.session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()
        avatarimg = Image.open(BytesIO(avatar_bytes)).convert("RGB")
        album_img = await self.get_album_img(lastfmdata.albumartlink)
        resized_album = self.resize_album_art(album_img)
        primary, secondary = dominant_colors(album_img.getvalue())
        draw, background = self.make_background(resized_album, primary)
        draw, background = self.draw_triangle(draw, background, secondary, avatarimg)
        text_color = self.get_text_color(primary)
        title_font = self.choose_title_font(lastfmdata.title)
        artist_album_font = self.choose_artist_album_fonts(
            lastfmdata.artist, lastfmdata.album
        )
        self.draw_text(
            draw,
            lastfmdata.title,
            lastfmdata.artist,
            lastfmdata.album,
            title_font,
            artist_album_font,
            text_color,
        )
        image = self.generate_image(background)

        return image

    def gif_to_png(self, gif):
        gif = Image.open(gif)
        output = BytesIO()
        gif.save(output, format="PNG")
        return output

    async def get_album_img(self, albumartlink):
        async with self.bot.session.get(albumartlink) as resp:
            if resp.status != 200:
                raise LastFMAlbumArtError(resp, albumartlink)
            album = BytesIO(await resp.read())
        if albumartlink.endswith(".gif"):
            album = self.gif_to_png(album)
        return album

    def resize_album_art(self, album):
        album = Image.open(album)
        return album.resize((124, 124), resample=Image.ANTIALIAS)

    def color_analysis(self, album, clusters=5):
        primary, secondary = dominant_colors(album, clusters)
        return primary, secondary

    def make_background(self, album, primary_color):
        background = Image.new("RGBA", (548, 147), tuple(primary_color))
        background.paste(album, (12, 12))
        draw = ImageDraw.Draw(background)
        return draw, background

    def draw_triangle(self, draw, background, secondary_color, avatar_img):
        draw.polygon([(548, 0), (401, 147), (548, 147)], tuple(secondary_color))
        avatar = self.mask_discord_avatar(avatar_img, avatar_img.size)
        avatar_scaled = avatar.resize((64, 64), resample=Image.Resampling.LANCZOS)
        background.paste(avatar_scaled, (473, 73), mask=avatar_scaled)
        return draw, background

    def mask_discord_avatar(self, image, size):
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([0, 0, size[0], size[1]], fill=255)
        result = image.copy()
        result.putalpha(mask)
        return result

    def get_text_color(self, primary_color):
        if sum(primary_color) > 250:
            textcolor = BLACK
        else:
            textcolor = WHITE
        return textcolor

    def choose_artist_album_fonts(self, artist, album):
        if self.cjk_detect(artist) or self.cjk_detect(album):
            return ImageFont.truetype("fonts/NotoSansCJK-Regular.ttc", 14)
        else:
            return ImageFont.truetype("fonts/NotoSans-Regular.ttf", 14)

    def choose_title_font(self, title):
        if self.cjk_detect(title):
            return ImageFont.truetype("fonts/NotoSansCJK-Medium.ttc", 14)
        else:
            return ImageFont.truetype("fonts/NotoSans-SemiBold.ttf", 14)

    def draw_text(self, draw, title, artist, album, titlefont, artistfont, textcolor):
        draw.text(
            (146, 24),
            self.wrap_text(title, titlefont, 350, False),
            textcolor,
            font=titlefont,
        )
        draw.text(
            (146, 73),
            self.wrap_text(artist, artistfont, 312, True),
            textcolor,
            font=artistfont,
        )
        draw.text(
            (146, 96),
            self.wrap_text(album, artistfont, 280, False),
            textcolor,
            font=artistfont,
        )

    def generate_image(self, background):
        arr = BytesIO()
        background.save(arr, format="PNG")
        arr.seek(0)
        return arr

    def cjk_detect(self, text):
        # korean
        if re.search("[\uac00-\ud7a3]", text):
            return True
        # japanese
        if re.search("[\u3040-\u30ff]", text):
            return True
        # chinese
        if re.search("[\u4e00-\u9FFF]", text):
            return True
        return None

    def wrap_text(self, text, font, max_width, is_artist):
        if font.getsize(text)[0] < max_width:
            return text
        else:
            lines = []
            words = text.split()
            count = 0
            while count < len(words):
                line = ""
                while (
                    count < len(words)
                    and font.getsize(line + words[count])[0] < max_width
                ):
                    line = line + words[count] + " "
                    count += 1
                if not line:
                    line = words[count]
                    count += 1
                lines.append(line)
        if len(lines) > 2 and not is_artist:
            return lines[0] + "\n" + lines[1][:-4] + "..."
        if len(lines) > 1 and is_artist:
            return lines[0][:-4] + "..."
        else:
            return lines[0] + "\n" + lines[1]


async def setup(bot):
    await bot.add_cog(Fmi(bot))
