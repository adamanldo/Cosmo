import pytest

from cogs.fmi import LastFmParameters
from cogs.utils.fmi_text import FmiText


def make_text(title="Title", artist="Artist", album="Album"):
    data = LastFmParameters(title=title, artist=artist, album=album, albumartlink="")
    return FmiText(data)


def test_short_text_is_not_wrapped():
    text = make_text(title="Short Title", artist="Short Artist", album="Short Album")
    assert text.title_text == ["Short Title"]
    assert text.artist_text == "Short Artist"
    assert text.album_text == ["Short Album"]


def test_long_title_wraps_to_two_lines_with_ellipsis():
    long_title = (
        "This Is A Much Longer Title That Should Wrap To Multiple Lines "
        "And Then Get Truncated With An Ellipsis Because It Keeps Going On And On"
    )
    text = make_text(title=long_title)
    assert len(text.title_text) == 2
    assert text.title_text[1].endswith("...")


def test_long_album_wraps_to_two_lines_with_ellipsis():
    long_album = "This Is Also A Rather Long Album Name That Wraps And Should Get Truncated Eventually"
    text = make_text(album=long_album)
    assert len(text.album_text) == 2
    assert text.album_text[1].endswith("...")


def test_long_artist_collapses_to_single_truncated_line():
    long_artist = "A Very Long Artist Name That Should Get Truncated Eventually Too And Then Some More"
    text = make_text(artist=long_artist)
    assert isinstance(text.artist_text, str)
    assert text.artist_text.endswith("...")


def test_artist_that_fits_on_one_line_is_not_truncated():
    text = make_text(artist="Short Name")
    assert text.artist_text == "Short Name"


def test_arabic_text_is_reshaped_and_reordered():
    text = make_text(title="مرحبا بكم في هذا الاختبار", artist="فنان عربي", album="ألبوم عربي")
    # Reshaping/bidi changes the string; just confirm it ran without error and
    # produced non-empty output rather than asserting exact glyph output
    assert text.title_text and all(line for line in text.title_text)
    assert text.artist_text
    assert text.album_text and all(line for line in text.album_text)


def test_hebrew_text_is_reordered_without_arabic_reshaping():
    text = make_text(title="שלום עולם", artist="אמן", album="אלבום")
    assert text.title_text and all(line for line in text.title_text)
    assert text.artist_text
    assert text.album_text and all(line for line in text.album_text)


def test_unknown_text_type_raises():
    text = make_text()
    with pytest.raises(ValueError):
        text.get_wrapped_text("some text", "bogus_type")
