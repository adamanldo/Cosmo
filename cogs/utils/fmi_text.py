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
            wrapped = ipy.text_wrap(
                text,
                350,
                self.font_size,
                self.bold_fonts,
            )

            if len(wrapped) > 2:
                wrapped = wrapped[:2]
                wrapped[1] = wrapped[1][:-3] + "..."

        if text_type == "artist":
            wrapped = ipy.text_wrap(
                text,
                312,
                self.font_size,
                self.regular_fonts,
                wrap_style=ipy.WrapStyle.Character,
            )

            if len(wrapped) > 1:
                wrapped = wrapped[0]
                wrapped = wrapped[:-3] + "..."
            else:
                wrapped = wrapped[0]

        if text_type == "album":
            wrapped = ipy.text_wrap(
                text,
                280,
                self.font_size,
                self.regular_fonts,
            )

            if len(wrapped) > 2:
                wrapped = wrapped[:2]
                wrapped[1] = wrapped[1][:-3] + "..."

        return wrapped
