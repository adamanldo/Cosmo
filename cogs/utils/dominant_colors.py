import colour
import cv2
import numpy as np
from skimage.color import lab2rgb
from sklearn.cluster import KMeans


def lab_to_rgb(color):
    lab = [[[color[0], color[1], color[2]]]]
    rgb = lab2rgb(lab)[0][0]
    return [int(np.clip(c * 255, 0, 255)) for c in rgb]


def dominant_colors(image, clusters=5):
    img = np.frombuffer(image, dtype=np.uint8)
    img = cv2.imdecode(img, cv2.IMREAD_UNCHANGED)

    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif len(img.shape) == 3 and img.shape[2] == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    img = cv2.cvtColor(img.astype(np.float32) / 255, cv2.COLOR_BGR2LAB)
    img = img.reshape((img.shape[0] * img.shape[1], 3))

    cluster = KMeans(n_clusters=clusters, tol=0.001, random_state=42)
    cluster.fit(img)

    colors = cluster.cluster_centers_
    labels = cluster.labels_

    labels = list(labels)
    percent = []
    for i in range(len(colors)):
        j = labels.count(i)
        j = j / len(labels)
        percent.append(j)

    percent = np.array(percent)
    colors = colors[(-percent).argsort()]

    counter = 1
    primary = colors[0]
    secondary = colors[counter]

    highest_delta_e_counter = 1
    delta_e = colour.difference.delta_E_CIE2000(primary, secondary)
    highest_delta_e = delta_e

    if delta_e < 20:
        while delta_e < 20 and counter < 4:
            counter += 1
            secondary = colors[counter]
            delta_e = colour.difference.delta_E_CIE2000(primary, secondary)
            if delta_e > highest_delta_e:
                highest_delta_e = delta_e
                highest_delta_e_counter = counter
    secondary = colors[highest_delta_e_counter]

    return lab_to_rgb(primary), lab_to_rgb(secondary)


# --- v2: vibrant color preference ---

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


def dominant_colors_v2(
    image,
    clusters=5,
    min_delta_e=8,
    min_percentage=0.02,
    min_chroma=12,
):
    img = np.frombuffer(image, dtype=np.uint8)
    img = cv2.imdecode(img, cv2.IMREAD_UNCHANGED)

    if len(img.shape) == 2 or (len(img.shape) == 3 and img.shape[2] == 1):
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    img = cv2.cvtColor(img.astype(np.float32) / 255, cv2.COLOR_BGR2LAB)
    img = img.reshape((-1, 3))

    cluster = KMeans(n_clusters=clusters, tol=0.001, random_state=42)
    cluster.fit(img)

    colors = cluster.cluster_centers_
    labels = cluster.labels_

    percent = np.array([(labels == i).sum() / len(labels) for i in range(len(colors))])
    order = (-percent).argsort()
    colors = colors[order]
    percent = percent[order]

    primary = colors[0]

    lch = [_lab_to_lch(c) for c in colors]
    hues = np.array([h for _, _, h in lch])
    chromas = np.array([C for _, C, _ in lch])

    candidates = []

    for i in range(1, len(colors)):
        if percent[i] < min_percentage:
            continue

        delta_e = colour.difference.delta_E_CIE2000(primary, colors[i])
        if delta_e < min_delta_e:
            continue

        L, C, h = lch[i]
        if C < min_chroma:
            continue

        delta_norm = delta_e / 50.0
        chroma_norm = _chroma_boost(C)
        freq_norm = np.sqrt(percent[i])
        lightness_norm = _lightness_weight(L)
        hue_opp = _hue_opposition_boost(_hue_distance(lch[0][2], h))
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
        # Relax min_percentage but keep chroma — prevents white/gray winning on dark albums
        for i in range(1, len(colors)):
            delta_e = colour.difference.delta_E_CIE2000(primary, colors[i])
            if delta_e < min_delta_e:
                continue
            L, C, h = lch[i]
            if C < min_chroma:
                continue
            score = 0.5 * _chroma_boost(C) + 0.5 * (delta_e / 50.0)
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
