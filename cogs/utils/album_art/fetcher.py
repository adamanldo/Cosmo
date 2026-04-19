import asyncio
import logging
import time

import aiohttp

log = logging.getLogger(__name__)

_spotify_token: str | None = None
_spotify_token_expires: float = 0.0

# Last.fm serves this hash as the URL when no real art exists
_LASTFM_PLACEHOLDER = "2a96cbd8b46e442fc41c2b86b821562f"

_LASTFM_TIMEOUT = aiohttp.ClientTimeout(sock_connect=3, total=8)
_SPOTIFY_API_TIMEOUT = aiohttp.ClientTimeout(total=5)
_SPOTIFY_IMG_TIMEOUT = aiohttp.ClientTimeout(total=8)


async def _get_spotify_token(session, client_id, client_secret):
    global _spotify_token, _spotify_token_expires
    if _spotify_token and time.monotonic() < _spotify_token_expires - 60:
        return _spotify_token

    try:
        async with session.post(
            "https://accounts.spotify.com/api/token",
            auth=aiohttp.BasicAuth(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            timeout=_SPOTIFY_API_TIMEOUT,
        ) as resp:
            if resp.status != 200:
                log.warning("Spotify token request failed with status %s", resp.status)
                return None
            js = await resp.json()
            _spotify_token = js["access_token"]
            _spotify_token_expires = time.monotonic() + js["expires_in"]
            log.debug("Refreshed Spotify access token")
            return _spotify_token
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        log.warning("Failed to get Spotify token: %s", e)
    except Exception as e:
        log.exception("Unexpected error getting Spotify token: %s", e)
    return None


async def _fetch_spotify_art(session, artist, album, client_id, client_secret):
    if not client_id or not client_secret:
        return None

    token = await _get_spotify_token(session, client_id, client_secret)
    if not token:
        return None

    try:
        params = {"q": f"album:{album} artist:{artist}", "type": "album", "limit": 1}
        headers = {"Authorization": f"Bearer {token}"}
        async with session.get(
            "https://api.spotify.com/v1/search",
            headers=headers,
            params=params,
            timeout=_SPOTIFY_API_TIMEOUT,
        ) as resp:
            if resp.status != 200:
                log.debug("Spotify search returned status %s", resp.status)
                return None
            js = await resp.json()

        items = js.get("albums", {}).get("items", [])
        if not items:
            log.debug("No Spotify results for %s / %s", artist, album)
            return None

        images = items[0].get("images", [])
        if not images:
            return None

        image_url = images[0]["url"]  # Spotify sorts images largest-first
        async with session.get(image_url, timeout=_SPOTIFY_IMG_TIMEOUT) as resp:
            if resp.status == 200:
                content = await resp.read()
                log.info("Fetched album art from Spotify for %s / %s", artist, album)
                return content
            log.debug("Spotify image fetch returned status %s", resp.status)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        log.warning("Spotify art fetch failed for %s / %s: %s", artist, album, e)
    except Exception as e:
        log.exception("Unexpected error fetching Spotify art for %s / %s: %s", artist, album, e)

    return None


async def fetch_album_bytes(
    session, artist, album, lastfm_url, spotify_client_id=None, spotify_client_secret=None
):
    if lastfm_url and _LASTFM_PLACEHOLDER not in lastfm_url:
        for attempt in range(2):
            try:
                async with session.get(lastfm_url, timeout=_LASTFM_TIMEOUT) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        log.info("Fetched album art from Last.fm")
                        return content
                    log.debug("Last.fm returned status %s", resp.status)
                    break
            except asyncio.TimeoutError:
                if attempt == 0:
                    log.warning("Timeout fetching from Last.fm URL, retrying...")
                else:
                    log.warning("Last.fm URL timed out after retry")
            except aiohttp.ClientError as e:
                log.warning("Last.fm fetch error: %s", e)
                break

    spotify_bytes = await _fetch_spotify_art(
        session, artist, album, spotify_client_id, spotify_client_secret
    )
    if spotify_bytes:
        return spotify_bytes

    log.warning("No album artwork found for %s / %s", artist, album)
    return None


async def fetch_avatar_bytes(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                return await resp.read()
            log.warning("Avatar fetch returned status %s", resp.status)
    except asyncio.TimeoutError:
        log.warning("Timeout fetching avatar from %s", url)
    except Exception as e:
        log.exception("Error fetching avatar: %s", e)
    return None
