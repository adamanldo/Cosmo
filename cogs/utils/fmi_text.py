import re
import imagetext_py as ipy
import arabic_reshaper
from bidi.algorithm import get_display


class FmiText:
    ipy.FontDB.LoadFromDir("./fonts")
    regular_fonts = ipy.FontDB.Query(
        "NotoSans-Regular NotoSansHK-Regular NotoSansJP-Regular NotoSansKR-Regular NotoSansSC-Regular "
        + "NotoSansTC-Regular NotoSansArabic-Regular Heebo-Regular NotoEmoji-Regular Symbola Unifont"
    )
    bold_fonts = ipy.FontDB.Query(
        "NotoSans-SemiBold NotoSansJP-Medium NotoSansKR-Medium NotoSansSC-Medium "
        + "NotoSansTC-Medium NotoSansArabic-SemiBold Heebo-SemiBold NotoEmoji-Medium Symbola Unifont"
    )

    def __init__(self, lastfmdata):
        self.font_size = 19
        self.title_text = self.process_text(lastfmdata.title, text_type="title")
        self.artist_text = self.process_text(lastfmdata.artist, text_type="artist")
        self.album_text = self.process_text(lastfmdata.album, text_type="album")

    def contains_arabic(self, text):
        return bool(re.search("[\u0600-\u06ff]", text))

    def is_rtl_language(self, text):
        return bool(
            re.search("[\u0600-\u06ff]", text) or re.search("[\u0590-\u05fe]", text)
        )

    def reshape_arabic_text(self, text):
        return arabic_reshaper.reshape(text)

    def process_text(self, text, text_type):
        if self.is_rtl_language(text):
            if self.contains_arabic(text):
                text = self.reshape_arabic_text(text)
            text = get_display(text)
        return self.get_wrapped_text(text, text_type)

    def get_wrapped_text(self, text, text_type):
        if text_type == "title":
            return self._wrap_lines(text, width=350, font=self.bold_fonts)
        elif text_type == "album":
            return self._wrap_lines(text, width=280, font=self.regular_fonts)
        elif text_type == "artist":
            return self._wrap_single_line(text, width=312, font=self.regular_fonts)
        raise ValueError(f"Unknown text_type: {text_type!r}")

    def _wrap_lines(self, text, width, font, max_lines=2):
        """Word-wrap into at most `max_lines` lines, ellipsizing the last one if truncated."""
        lines = ipy.text_wrap(text, width, self.font_size, font)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1][:-3] + "..."
        return lines

    def _wrap_single_line(self, text, width, font):
        """Character-wrap and keep only the first line, ellipsizing it if more would follow."""
        lines = ipy.text_wrap(
            text, width, self.font_size, font, wrap_style=ipy.WrapStyle.Character
        )
        first_line = lines[0]
        if len(lines) > 1:
            first_line = first_line[:-3] + "..."
        return first_line
