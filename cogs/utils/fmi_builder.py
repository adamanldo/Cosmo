from io import BytesIO
import imagetext_py as ipy
from PIL import Image, ImageDraw

from .dominant_colors import dominant_colors


BLACK = ipy.Paint.Color((0, 0, 0, 255))
WHITE = ipy.Paint.Color((255, 255, 255, 255))


class FmiBuilder:
    def __init__(self, album_bytes, avatar_bytes, text):
        self._primary, self._secondary = dominant_colors(album_bytes.getvalue())
        self._avatar_image = self.mask_and_resize_discord_avatar(avatar_bytes)
        self._album_image = Image.open(album_bytes).resize(
            (124, 124), resample=Image.ANTIALIAS
        )
        self._text = text
        self._text_color = self.get_text_color(self._primary)
        self._background = Image.new("RGBA", (548, 147), tuple(self._primary))
        self._background_draw = ImageDraw.Draw(self._background)

    def create_fmi(self):
        # Paste the album image
        self._background.paste(self._album_image, (12, 12))

        # Draw the triangle, paste the user's avatar
        self._background_draw.polygon(
            [(548, 0), (401, 147), (548, 147)], tuple(self._secondary)
        )
        self._background.paste(self._avatar_image, (473, 73), mask=self._avatar_image)

        with ipy.Writer(self._background) as w:
            w.draw_text_multiline(
                text=self._text.title_text,
                x=146,
                y=24,
                ax=0,
                ay=0,
                width=350,
                size=self._text.font_size,
                font=self._text.bold_fonts,
                fill=self._text_color,
            )
            w.draw_text(
                text=self._text.artist_text,
                x=146,
                y=73,
                size=self._text.font_size,
                font=self._text.regular_fonts,
                fill=self._text_color,
            )
            w.draw_text_multiline(
                text=self._text.album_text,
                x=146,
                y=96,
                ax=0,
                ay=0,
                width=280,
                size=self._text.font_size,
                font=self._text.regular_fonts,
                fill=self._text_color,
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
            text_color = BLACK
        else:
            text_color = WHITE
        return text_color
