from io import BytesIO
import imagetext_py as ipy
from PIL import Image, ImageDraw
from .dominant_colors import dominant_colors


BLACK = ipy.Paint.Color((0, 0, 0, 255))
WHITE = ipy.Paint.Color((255, 255, 255, 255))


class FmiBuilder:

    ipy.FontDB.LoadFromDir("./fonts")
    regular_fonts = ipy.FontDB.Query(
        "NotoSans-Regular NotoSansHK-Regular NotoSansJP-Regular NotoSansKR-Regular NotoSansSC-Regular "
        + "NotoSansTC-Regular NotoSansArabic-Regular Heebo-Regular Symbola"
    )
    bold_fonts = ipy.FontDB.Query(
        "NotoSans-SemiBold NotoSansJP-Medium NotoSansKR-Medium NotoSansSC-Medium "
        + "NotoSansTC-Medium NotoSansArabic-SemiBold Heebo-SemiBold Symbola"
    )

    def __init__(self, album_bytes, avatar_bytes):
        self._primary, self._secondary = dominant_colors(album_bytes.getvalue())
        self._avatar = self.mask_and_resize_discord_avatar(avatar_bytes)
        self._album = Image.open(album_bytes).resize(
            (124, 124), resample=Image.ANTIALIAS
        )
        self._font_size = 19
        self._background = Image.new("RGBA", (548, 147), tuple(self._primary))
        self._background_draw = ImageDraw.Draw(self._background)

    def create_fmi(self, lastfmdata):
        # Paste the album image
        self._background.paste(self._album, (12, 12))

        # Draw the triangle, paste the user's avatar
        self._background_draw.polygon(
            [(548, 0), (401, 147), (548, 147)], tuple(self._secondary)
        )
        self._background.paste(self._avatar, (473, 73), mask=self._avatar)

        text_color = self.get_text_color(self._primary)

        title_wrapped, artist_wrapped, album_wrapped = self.get_wrapped_text(
            lastfmdata.title, lastfmdata.artist, lastfmdata.album
        )

        with ipy.Writer(self._background) as w:
            w.draw_text_multiline(
                text=title_wrapped,
                x=146,
                y=24,
                ax=0,
                ay=0,
                width=350,
                size=self._font_size,
                font=self.bold_fonts,
                fill=text_color,
            )
            w.draw_text(
                text=artist_wrapped,
                x=146,
                y=73,
                size=self._font_size,
                font=self.regular_fonts,
                fill=text_color,
            )
            w.draw_text_multiline(
                text=album_wrapped,
                x=146,
                y=96,
                ax=0,
                ay=0,
                width=280,
                size=self._font_size,
                font=self.regular_fonts,
                fill=text_color,
            )

        arr = BytesIO()
        self._background.save(arr, format="PNG")
        arr.seek(0)
        return arr

    # Masks and resizes discord avatar so it's ready to draw onto the background
    def mask_and_resize_discord_avatar(self, avatar_bytes):
        avatar = Image.open(avatar_bytes).convert("RGB")
        mask = Image.new("L", avatar.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([0, 0, avatar.size[0], avatar.size[1]], fill=255)
        result = avatar.copy()
        result.putalpha(mask)
        resized = result.resize((64, 64), resample=Image.Resampling.LANCZOS)
        return resized

    def get_text_color(self, primary_color):
        if sum(primary_color) > 250:
            textcolor = BLACK
        else:
            textcolor = WHITE
        return textcolor

    def get_wrapped_text(self, title, artist, album):
        title_wrapped = ipy.text_wrap(
            title,
            350,
            self._font_size,
            self.bold_fonts,
        )

        if len(title_wrapped) > 2:
            title_wrapped = title_wrapped[:2]
            title_wrapped[1] = title_wrapped[1][:-4] + "..."

        artist_wrapped = ipy.text_wrap(
            artist,
            312,
            self._font_size,
            self.regular_fonts,
        )

        if len(artist_wrapped) > 1:
            artist_wrapped = artist_wrapped[0]
            artist_wrapped = artist_wrapped[:-4] + "..."
        else:
            artist_wrapped = artist_wrapped[0]

        album_wrapped = ipy.text_wrap(
            album,
            280,
            self._font_size,
            self.regular_fonts,
        )

        if len(album_wrapped) > 2:
            album_wrapped = album_wrapped[:2]
            album_wrapped[1] = album_wrapped[1][:-4] + "..."

        return title_wrapped, artist_wrapped, album_wrapped
