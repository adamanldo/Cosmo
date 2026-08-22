import numpy as np
import pytest
from skimage.color import rgb2lab

from cogs.utils.dominant_colors import (
    _chroma_boost,
    _hue_distance,
    _hue_opposition_boost,
    _lab_to_lch,
    _lightness_weight,
    _merge_similar_clusters,
    _oklab_chroma,
    _select_primary_index,
)


def lab_of(rgb):
    return rgb2lab(np.array([[rgb]], dtype=float) / 255)[0][0]


# --- _hue_distance ---


@pytest.mark.parametrize(
    "h1, h2, expected",
    [
        (10, 350, 20),  # wraps around 0/360 the short way
        (0, 180, 180),  # exact opposite
        (45, 45, 0),  # identical
        (350, 10, 20),  # symmetric
    ],
)
def test_hue_distance_wraps_correctly(h1, h2, expected):
    assert _hue_distance(h1, h2) == pytest.approx(expected)


# --- _chroma_boost / _lightness_weight / _hue_opposition_boost ---


def test_chroma_boost_is_zero_at_zero_and_saturates_toward_one():
    assert _chroma_boost(0) == 0
    assert _chroma_boost(1000) == pytest.approx(1.0, abs=1e-6)


def test_lightness_weight_peaks_at_center():
    assert _lightness_weight(55) == pytest.approx(1.0)
    assert _lightness_weight(55) > _lightness_weight(0)
    assert _lightness_weight(55) > _lightness_weight(100)


def test_hue_opposition_boost_peaks_at_150_degrees():
    assert _hue_opposition_boost(150) == pytest.approx(1.0)
    assert _hue_opposition_boost(150) > _hue_opposition_boost(0)
    assert _hue_opposition_boost(150) > _hue_opposition_boost(360)


# --- _lab_to_lch ---


def test_lab_to_lch_matches_known_conversion():
    # a=3, b=4 -> chroma 5 (3-4-5 triangle), hue = atan2(4, 3) = ~53.13 degrees
    L, C, h = _lab_to_lch((50, 3, 4))
    assert L == 50
    assert C == pytest.approx(5.0)
    assert h == pytest.approx(53.13, abs=0.01)


# --- _oklab_chroma ---
# Reference values cross-checked against Björn Ottosson's published Oklab
# conversions for sRGB primaries.


@pytest.mark.parametrize(
    "rgb, expected_chroma",
    [
        ((255, 0, 0), 0.2577),
        ((0, 0, 255), 0.3132),
    ],
)
def test_oklab_chroma_matches_reference_values(rgb, expected_chroma):
    chroma = _oklab_chroma(np.array([lab_of(rgb)]))[0]
    assert chroma == pytest.approx(expected_chroma, abs=0.001)


def test_oklab_chroma_of_gray_is_near_zero():
    chroma = _oklab_chroma(np.array([lab_of((128, 128, 128))]))[0]
    assert chroma == pytest.approx(0.0, abs=0.01)


def test_oklab_chroma_handles_batches():
    colors = np.array([lab_of((255, 0, 0)), lab_of((0, 0, 255))])
    chromas = _oklab_chroma(colors)
    assert chromas.shape == (2,)
    assert chromas[0] == pytest.approx(0.2577, abs=0.001)
    assert chromas[1] == pytest.approx(0.3132, abs=0.001)


# --- _merge_similar_clusters ---


def test_merge_leaves_distinct_colors_untouched():
    colors = [lab_of((255, 0, 0)), lab_of((0, 0, 255))]
    percent = [0.6, 0.4]
    peak_chroma = [0.2, 0.3]
    merged_colors, merged_percent, merged_peak = _merge_similar_clusters(
        colors, percent, peak_chroma, threshold=15
    )
    assert len(merged_colors) == 2


def test_merge_fuses_near_identical_colors():
    # A third, clearly distinct color is included so the floor of 2 clusters
    # (see test_merge_never_collapses_below_two_clusters) doesn't itself
    # prevent the near-duplicate pair from merging -- with only 2 starting
    # clusters the merge loop never runs at all, regardless of distance,
    # since real usage always starts from KMeans' full cluster count.
    a = lab_of((100, 100, 100))
    b = lab_of((102, 102, 102))
    distinct = lab_of((0, 0, 255))
    colors = [a, b, distinct]
    percent = [0.5, 0.3, 0.2]
    peak_chroma = [0.1, 0.2, 0.3]
    merged_colors, merged_percent, merged_peak = _merge_similar_clusters(
        colors, percent, peak_chroma, threshold=15
    )
    assert len(merged_colors) == 2
    assert merged_percent[0] == pytest.approx(0.8)  # the merged near-duplicate pair
    assert merged_peak[0] == pytest.approx(0.2)  # takes the max of the two


def test_merge_weighted_average_is_correct():
    # Two colors along the L axis, close enough to merge; merged L should be
    # the percent-weighted average, not a plain midpoint. A third, distinct
    # color keeps the merge loop from being skipped entirely (see above).
    a = (20.0, 0.0, 0.0)
    b = (30.0, 0.0, 0.0)
    distinct = (80.0, 40.0, -40.0)
    colors = [a, b, distinct]
    percent = [0.36, 0.24, 0.4]
    peak_chroma = [0.0, 0.0, 0.3]
    merged_colors, merged_percent, _ = _merge_similar_clusters(
        colors, percent, peak_chroma, threshold=15
    )
    assert len(merged_colors) == 2
    merged = merged_colors[np.argmax(merged_percent)]
    assert merged[0] == pytest.approx(24.0)  # (0.36*20 + 0.24*30) / 0.6


def test_merge_never_collapses_below_two_clusters():
    # Regression test: on tonally narrow covers, every pairwise distance can
    # fall under threshold. Merging must never collapse to a single cluster,
    # or secondary ends up identical to primary (the cover.jpg bug).
    base = np.array([30.0, 5.0, 5.0])
    colors = [tuple(base + np.array([i * 2.0, i * 0.5, i * 0.5])) for i in range(5)]
    percent = [0.3, 0.25, 0.2, 0.15, 0.1]
    peak_chroma = [0.05] * 5
    merged_colors, merged_percent, _ = _merge_similar_clusters(
        colors, percent, peak_chroma, threshold=15
    )
    assert len(merged_colors) >= 2


# --- _select_primary_index ---


def test_select_primary_index_protects_landslide_dominant_background():
    # A near-black background covering 90% of the image must not be outvoted
    # by a small, more colorful cluster (Carly Rae Jepsen / Astral Weeks case)
    percent = np.array([0.90, 0.05, 0.05])
    lch = [(5.0, 1.0, 0.0), (50.0, 40.0, 90.0), (50.0, 40.0, 180.0)]
    assert _select_primary_index(percent, lch, min_chroma=12) == 0


def test_select_primary_index_picks_real_color_over_incoherent_dark_blend():
    # Regression test for an old bug: the real accent color (index
    # 3, chroma 50.9) must win even though it ranks 4th by raw frequency,
    # behind two separate near-black/near-white clusters and a small
    # leftover dark-grey sliver that happens to rank 3rd.
    percent = np.array([0.428, 0.367, 0.097, 0.070, 0.038])
    lch = [
        (12.0, 0.4, 195.0),  # near-black
        (94.6, 1.7, 100.0),  # near-white
        (42.0, 9.6, 50.0),  # leftover dark-grey sliver (must NOT win)
        (50.5, 50.9, 42.0),  # the real accent color (must win)
        (83.0, 32.6, 86.0),
    ]
    assert _select_primary_index(percent, lch, min_chroma=12) == 3


def test_select_primary_index_close_race_prefers_higher_chroma():
    percent = np.array([0.5, 0.4])
    lch = [(30.0, 2.0, 0.0), (50.0, 30.0, 120.0)]
    assert _select_primary_index(percent, lch, min_chroma=12) == 1


def test_select_primary_index_above_landslide_ratio_stays_dominant():
    percent = np.array([0.62, 0.4])  # ratio 1.55, clearly above the 1.5 cutoff
    lch = [(10.0, 1.0, 0.0), (50.0, 40.0, 90.0)]
    assert _select_primary_index(percent, lch, min_chroma=12, landslide_ratio=1.5) == 0


def test_select_primary_index_below_landslide_ratio_triggers_override():
    percent = np.array([0.58, 0.4])  # ratio 1.45, clearly below the 1.5 cutoff
    lch = [(10.0, 1.0, 0.0), (50.0, 40.0, 90.0)]
    assert _select_primary_index(percent, lch, min_chroma=12, landslide_ratio=1.5) == 1


def test_select_primary_index_single_cluster_is_safe():
    percent = np.array([1.0])
    lch = [(10.0, 1.0, 0.0)]
    assert _select_primary_index(percent, lch, min_chroma=12) == 0
