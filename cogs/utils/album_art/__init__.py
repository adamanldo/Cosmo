import logging

from .decoder import decode_image_from_bytes, validate_image_bytes
from .fetcher import fetch_album_bytes

log = logging.getLogger(__name__)


async def get_album_image(
    session, artist, album, lastfm_url, spotify_client_id=None, spotify_client_secret=None
):
    try:
        img_bytes = await fetch_album_bytes(
            session, artist, album, lastfm_url, spotify_client_id, spotify_client_secret
        )
    except Exception as e:
        log.exception("Failed to fetch album bytes for %s / %s: %s", artist, album, e)
        return None

    if not img_bytes:
        log.info("No album bytes found for %s / %s", artist, album)
        return None

    if not validate_image_bytes(img_bytes):
        log.warning("Image validation failed for %s / %s", artist, album)
        return None

    try:
        return decode_image_from_bytes(img_bytes)
    except Exception as e:
        log.exception("Failed to decode album image for %s / %s: %s", artist, album, e)
        return None
