from itertools import combinations

import colour
import cv2
import numpy as np
from skimage.color import lab2rgb
from sklearn.cluster import KMeans


def lab_to_rgb(color):
    lab = [[[color[0], color[1], color[2]]]]
    rgb = lab2rgb(lab)[0][0]
    return [int(np.clip(c * 255, 0, 255)) for c in rgb]


def _srgb_to_linear(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _oklab_chroma(lab_colors):
    # Oklab (Ottosson 2020) is more perceptually uniform than CIELAB, which is
    # documented to under-represent blue saturation relative to how vivid it
    # actually looks to people. Used only as the vibrancy signal in scoring;
    # clustering and distance-from-primary stay in CIELAB/CIEDE2000, which
    # aren't shown to have a problem.
    lab_colors = np.atleast_2d(lab_colors)
    rgb = lab2rgb(lab_colors.reshape(-1, 1, 3)).reshape(-1, 3)
    r, g, b = _srgb_to_linear(rgb).T
    lms_l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = np.cbrt(lms_l), np.cbrt(m), np.cbrt(s)
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    ok_b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return np.sqrt(a**2 + ok_b**2)


def _chroma_boost(c, scale=40):
    return np.tanh(c / scale)


def _lightness_weight(L, center=55, spread=25):
    return np.exp(-(((L - center) / spread) ** 2))


def _lab_to_lch(color):
    L, a, b = color
    C = np.sqrt(a**2 + b**2)
    h = (np.degrees(np.arctan2(b, a)) + 360) % 360
    return L, C, h


def _hue_distance(h1, h2):
    d = abs(h1 - h2)
    return min(d, 360 - d)


def _hue_opposition_boost(d):
    return np.exp(-(((d - 150) / 40) ** 2))


def _hue_density(target_h, hues, chromas, bandwidth=20):
    dists = np.array([_hue_distance(target_h, h) for h in hues])
    weights = np.exp(-((dists / bandwidth) ** 2))
    return np.sum(weights * chromas)


def _hue_isolation_bonus(h, hues, chromas):
    density = _hue_density(h, hues, chromas)
    return 1.0 / (1.0 + density)


def _merge_similar_clusters(colors, percent, peak_chroma, threshold):
    # On smooth-gradient covers, KMeans slices the gradient into several
    # near-duplicate clusters with near-tied sizes, so ranking by raw cluster
    # size makes the "primary" pick flip on essentially arbitrary partition
    # boundaries whenever `clusters` changes. Fusing clusters that are barely
    # distinguishable before ranking makes the pick track the true macro color
    # regions instead.
    colors = np.asarray(colors, dtype=float)
    percent = np.asarray(percent, dtype=float)
    peak_chroma = np.asarray(peak_chroma, dtype=float)

    # Never merge down to a single cluster: on tonally narrow covers (e.g. all
    # dark, desaturated tones) every pairwise distance can fall under
    # threshold, collapsing everything into one color and leaving nothing
    # distinct for secondary to be picked from -- it would end up identical
    # to primary. Always leave at least two clusters so that can't happen.
    while len(colors) > 2:
        delta_e, i, j = min(
            (colour.difference.delta_E_CIE2000(colors[a], colors[b]), a, b)
            for a, b in combinations(range(len(colors)), 2)
        )
        if delta_e >= threshold:
            break

        merged_color = (colors[i] * percent[i] + colors[j] * percent[j]) / (percent[i] + percent[j])
        merged_percent = percent[i] + percent[j]
        merged_peak_chroma = max(peak_chroma[i], peak_chroma[j])
        colors = np.vstack([np.delete(colors, (i, j), axis=0), merged_color])
        percent = np.append(np.delete(percent, (i, j)), merged_percent)
        peak_chroma = np.append(np.delete(peak_chroma, (i, j)), merged_peak_chroma)

    order = np.argsort(-percent)
    return colors[order], percent[order], peak_chroma[order]


def _select_primary_index(percent, lch, min_chroma, landslide_ratio=1.5):
    # The most-frequent cluster is usually the primary color, but not always:
    # on busy photographic covers, many visually unrelated dark/shadowed
    # regions (shadows on different objects, foliage, clothing) often land
    # close together in Lab space purely because they're all dark and
    # desaturated, not because they're really "the same color" — so they can
    # outnumber a real, uniform design color (e.g. a printed banner) by sheer
    # pixel count. When the top-frequency cluster is low-chroma and not an
    # overwhelming landslide over the runner-up, prefer whichever cluster best
    # combines real size with an actual, trustworthy color. All clusters are
    # eligible here, not just the most frequent few: which cluster a busy dark
    # background happens to fragment into is incidental (a slightly different
    # scan/compression of the same photo can shift it), and can otherwise
    # shove the real accent color just outside an arbitrary top-N window —
    # the landslide check below already protects a genuinely dominant
    # background from being outvoted by a small, high-chroma cluster.
    is_landslide = len(percent) < 2 or (percent[0] / percent[1]) >= landslide_ratio
    if lch[0][1] < min_chroma and not is_landslide:
        scores = [np.sqrt(percent[i]) * lch[i][1] for i in range(len(percent))]
        return int(np.argmax(scores))
    return 0


def dominant_colors(
    image,
    clusters=5,
    min_percentage=0.02,
    min_chroma=12,
    merge_threshold=15,
):
    # Decode the raw image bytes into a BGR numpy array
    img = np.frombuffer(image, dtype=np.uint8)
    img = cv2.imdecode(img, cv2.IMREAD_UNCHANGED)

    # Ensure we always have a 3-channel BGR image (handle grayscale and BGRA input)
    if len(img.shape) == 2 or (len(img.shape) == 3 and img.shape[2] == 1):
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    # Downsample to ~40K pixels before clustering. This still gives a solid
    # speedup on large source images (e.g. Spotify's 640x640 art), but keeps
    # enough detail that small, highly-saturated regions (logos, text) survive
    # as their own cluster instead of blending into the background
    h, w = img.shape[:2]
    if h * w > 40000:
        scale = (40000 / (h * w)) ** 0.5
        img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)

    # Convert to CIELAB so that Euclidean distance between colors approximates
    # human perceptual difference, this makes the ΔE comparisons meaningful
    img = cv2.cvtColor(img.astype(np.float32) / 255, cv2.COLOR_BGR2LAB)
    img = img.reshape((-1, 3))

    # Cluster pixels into `clusters` representative colors
    cluster = KMeans(n_clusters=clusters, n_init=2, tol=0.001, random_state=42)
    cluster.fit(img)

    # Sort clusters by frequency (most dominant color first)
    colors = cluster.cluster_centers_
    counts = np.bincount(cluster.labels_, minlength=clusters)
    percent = counts / counts.sum()

    # A cluster's centroid can be diluted by anti-aliased/blended edge pixels
    # (e.g. thin text fading into a background) even when a genuinely vivid
    # color exists within it, so scoring vibrancy off the single averaged
    # center alone can unfairly punish small, saturated design elements.
    # Track each cluster's 90th-percentile member chroma (in Oklab) instead.
    peak_chroma = np.zeros(clusters)
    for i in range(clusters):
        members = img[cluster.labels_ == i]
        if len(members):
            peak_chroma[i] = np.percentile(_oklab_chroma(members), 90)

    order = (-percent).argsort()
    colors = colors[order]
    percent = percent[order]
    peak_chroma = peak_chroma[order]

    # Fuse clusters that are perceptually near-identical before ranking, see
    # _merge_similar_clusters for why this matters
    colors, percent, peak_chroma = _merge_similar_clusters(colors, percent, peak_chroma, merge_threshold)

    # Convert each cluster center to LCH (Lightness, Chroma, Hue) so we can
    # reason about saturation and hue angle independently
    lch = [_lab_to_lch(c) for c in colors]

    primary_idx = _select_primary_index(percent, lch, min_chroma)

    if primary_idx != 0:
        colors[[0, primary_idx]] = colors[[primary_idx, 0]]
        percent[[0, primary_idx]] = percent[[primary_idx, 0]]
        peak_chroma[[0, primary_idx]] = peak_chroma[[primary_idx, 0]]
        lch[0], lch[primary_idx] = lch[primary_idx], lch[0]

    primary = colors[0]
    hues = np.array([h for _, _, h in lch])
    chromas = np.array([C for _, C, _ in lch])

    # A near-neutral primary (common: black or white backgrounds) has no
    # meaningful hue — its hue angle is just rounding noise — so hue-opposition
    # scoring against it would reward/penalize candidates based on that noise
    primary_has_hue = lch[0][1] >= min_chroma

    # Score each remaining cluster as a secondary color candidate.
    # A good secondary is perceptually distinct, vibrant, reasonably frequent,
    # well-lit, and hue-contrasting with the primary.
    candidates = []

    for i in range(1, len(colors)):
        # Skip colors that barely appear in the image; likely noise
        if percent[i] < min_percentage:
            continue

        # _merge_similar_clusters already guarantees every surviving cluster is
        # at least merge_threshold away from the primary in delta E, so no
        # separate "too similar to primary" check is needed here
        delta_e = colour.difference.delta_E_CIE2000(primary, colors[i])

        L, C, h = lch[i]
        # Skip near-neutral colors (grays, whites, blacks), they make poor accents
        if C < min_chroma:
            continue

        # Weighted score combining perceptual distance, saturation, frequency,
        # lightness, hue opposition, and hue isolation. delta_norm is tanh-capped
        # like chroma_norm so it can't dominate the score for candidates that are
        # merely far in lightness from primary (e.g. anything vs. a near-black
        # or near-white primary) rather than genuinely vibrant
        delta_norm = np.tanh(delta_e / 50.0)
        chroma_norm = _chroma_boost(peak_chroma[i], scale=0.1)
        freq_norm = np.sqrt(percent[i])
        lightness_norm = _lightness_weight(L)
        hue_opp = _hue_opposition_boost(_hue_distance(lch[0][2], h)) if primary_has_hue else 1.0
        hue_iso = _hue_isolation_bonus(h, hues, chromas)

        score = (
            0.30 * delta_norm
            + 0.28 * chroma_norm
            + 0.12 * freq_norm
            + 0.05 * lightness_norm
            + 0.15 * hue_opp
            + 0.10 * hue_iso
        )

        candidates.append((score, i))

    if not candidates:
        # Relax min_percentage but keep chroma, prevents white/gray winning on dark albums
        for i in range(1, len(colors)):
            delta_e = colour.difference.delta_E_CIE2000(primary, colors[i])
            L, C, h = lch[i]
            if C < min_chroma:
                continue
            score = 0.5 * _chroma_boost(peak_chroma[i], scale=0.1) + 0.5 * np.tanh(delta_e / 50.0)
            candidates.append((score, i))

    if not candidates:
        # Last resort: highest delta-E regardless of chroma (truly achromatic image)
        fallback = [
            (colour.difference.delta_E_CIE2000(primary, colors[i]), i)
            for i in range(1, len(colors))
        ]
        secondary_idx = max(fallback, key=lambda x: x[0])[1] if fallback else 0
        secondary = colors[secondary_idx]
    else:
        secondary = colors[max(candidates, key=lambda x: x[0])[1]]

    return lab_to_rgb(primary), lab_to_rgb(secondary)
