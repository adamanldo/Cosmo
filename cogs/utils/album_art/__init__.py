import asyncio
import hashlib
import logging

from .decoder import decode_image_from_bytes, validate_image_bytes
from .fetcher import fetch_album_bytes

log = logging.getLogger(__name__)


async def get_album_image(session, cache, artist, album, lastfm_url):
    loop = asyncio.get_running_loop()
    key = hashlib.md5(f"{artist}:{album}".encode()).hexdigest()

    log.debug("Looking up album art for %s / %s (key: %s)", artist, album, key)

    try:
        cached = await loop.run_in_executor(None, cache.get, key)
        if cached:
            try:
                img_bytes_io = await loop.run_in_executor(
                    None, decode_image_from_bytes, cached
                )
                log.info("Retrieved album art from cache: %s / %s", artist, album)
                return img_bytes_io
            except Exception as e:
                log.warning("Failed to decode cached image, removing: %s", e)
                await loop.run_in_executor(None, cache.delete, key)
    except Exception as e:
        log.exception("Error checking cache for %s / %s: %s", artist, album, e)

    log.debug("Cache miss for %s / %s, fetching from remote", artist, album)
    try:
        img_bytes = await fetch_album_bytes(session, artist, album, lastfm_url)
    except Exception as e:
        log.exception("Failed to fetch album bytes for %s / %s: %s", artist, album, e)
        return None

    if not img_bytes:
        log.info("No album bytes found for %s / %s", artist, album)
        return None

    try:
        is_valid = await loop.run_in_executor(None, validate_image_bytes, img_bytes)
        if not is_valid:
            log.warning("Image validation failed for %s / %s", artist, album)
            return None
    except Exception as e:
        log.exception("Error validating image for %s / %s: %s", artist, album, e)
        return None

    try:
        img_bytes_io = await loop.run_in_executor(
            None, decode_image_from_bytes, img_bytes
        )
        await loop.run_in_executor(None, cache.set, key, img_bytes)
        log.info("Retrieved and cached album art: %s / %s", artist, album)
        return img_bytes_io
    except Exception as e:
        log.exception("Failed to decode album image for %s / %s: %s", artist, album, e)
        return None
