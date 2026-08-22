"""Golden-fixture tests against real album covers.

These assert hue-family + chroma-floor ranges rather than exact RGB values,
since exact-value assertions would be brittle against future library/BLAS
version drift and against deliberate future tuning of the algorithm. They
encode our current best judgment on these specific covers (all hand-verified
during development), not an objectively "correct" answer -- treat a failure
here as "did this change the outcome on a real cover," not automatically as
"something is broken."

Fixture images were obtained through the project's own Last.fm/Spotify
fetch path during development, at the low resolutions the bot itself
requests. 
"""

import os

import colour
import pytest
from skimage.color import rgb2lab

from cogs.utils.dominant_colors import _lab_to_lch, dominant_colors

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "album_art")


def load(filename):
    with open(os.path.join(FIXTURES_DIR, filename), "rb") as f:
        return f.read()


def lch_of(rgb):
    lab = rgb2lab([[[c / 255 for c in rgb]]])[0][0]
    return _lab_to_lch(lab)


def assert_is_near_neutral(rgb, max_chroma=12):
    _, C, _ = lch_of(rgb)
    assert C < max_chroma, f"expected a near-neutral color, got {rgb} (chroma={C:.1f})"


def assert_in_hue_family(rgb, hue_range, min_chroma=10):
    L, C, h = lch_of(rgb)
    assert C >= min_chroma, f"{rgb} is too washed out (chroma={C:.1f}) to be a real accent"
    lo, hi = hue_range
    assert lo <= h <= hi, f"{rgb} has hue {h:.0f}, expected within [{lo}, {hi}]"


@pytest.mark.parametrize(
    "filename, primary_check, secondary_hue_range",
    [
        # near-black backgrounds: primary must stay a near-neutral background,
        # not get pulled toward the secondary accent (regression: Astral Weeks)
        ("van_morrison_astral_weeks.png", "near_neutral", (90, 150)),  # green
        ("carly_rae_jepsen_emotion.png", "near_neutral", (10, 60)),  # orange
        # busy photographic cover: primary must be the real green banner, not
        # an incoherent blend of unrelated dark/shadowed regions (regression:
        # Pet Sounds)
        ("beach_boys_pet_sounds.png", (110, 170), (40, 90)),  # green primary, tan secondary
        # gradient cover: primary must land on the warm/light side of the
        # gradient consistently across cluster-count tuning (regression:
        # Steve Reich)
        ("steve_reich_pulse_quartet.png", (10, 70), (240, 310)),  # pink primary, navy secondary
        ("talk_talk_laughing_stock.png", (250, 320), (20, 70)),  # blue primary, peach secondary
        ("the_dismemberment_plan_e_and_i.png", (120, 190), (20, 70)),  # mint primary, orange secondary
    ],
)
def test_fixture_lands_in_expected_color_family(filename, primary_check, secondary_hue_range):
    primary, secondary = dominant_colors(load(filename))

    if primary_check == "near_neutral":
        assert_is_near_neutral(primary)
    else:
        assert_in_hue_family(primary, primary_check)

    assert_in_hue_family(secondary, secondary_hue_range)


def test_primary_and_secondary_are_never_identical():
    # Regression test: cover.jpg (a tonally narrow cover -- dark greys and
    # muted mauves) used to collapse to a single cluster, making secondary
    # identical to primary.
    for filename in os.listdir(FIXTURES_DIR):
        primary, secondary = dominant_colors(load(filename))
        assert primary != secondary, f"{filename}: primary and secondary are identical"


def test_near_duplicate_source_images_produce_consistent_primary():
    # Regression test: the same album's Last.fm and Spotify art are two
    # different scans/compressions of the same physical photo. A human sees
    # them as the same cover; the algorithm should agree closely too, not
    # produce two unrelated colors depending on which source happened to be
    # fetched (the Kurdish Cultural Music bug).
    primary_lastfm, secondary_lastfm = dominant_colors(
        load("kurdish_cultural_music_lastfm.png")
    )
    primary_spotify, secondary_spotify = dominant_colors(
        load("kurdish_cultural_music_spotify.png")
    )

    for rgb in (primary_lastfm, primary_spotify):
        assert_in_hue_family(rgb, (20, 70), min_chroma=30)

    lab_lastfm = rgb2lab([[[c / 255 for c in primary_lastfm]]])[0][0]
    lab_spotify = rgb2lab([[[c / 255 for c in primary_spotify]]])[0][0]
    delta_e = colour.difference.delta_E_CIE2000(lab_lastfm, lab_spotify)
    assert delta_e < 10, (
        f"primaries diverged too much between sources: {primary_lastfm} vs "
        f"{primary_spotify} (delta_E={delta_e:.1f})"
    )
