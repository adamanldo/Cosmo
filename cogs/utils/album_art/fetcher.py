import asyncio
import logging

import musicbrainzngs

log = logging.getLogger(__name__)

CAA_BASE = "https://coverartarchive.org/release"
MUSICBRAINZ_SEARCH_URL = "https://musicbrainz.org/ws/2/release/"


async def fetch_album_bytes(session, artist, album, lastfm_url):
    loop = asyncio.get_running_loop()

    async def fetch_caa_for_mbid(mbid):
        url = f"{CAA_BASE}/{mbid}/front-250"
        try:
            async with session.get(url, timeout=3) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    log.info("Fetched album art from CAA for MBID: %s", mbid)
                    return content
                else:
                    log.debug("CAA returned status %s for MBID: %s", resp.status, mbid)
        except asyncio.TimeoutError:
            log.warning("Timeout fetching from CAA for MBID: %s", mbid)
        except Exception as e:
            log.exception("Error fetching from CAA for MBID %s: %s", mbid, e)
        return None

    async def fetch_lastfm_art(lastfm_url):
        if not lastfm_url:
            return None
        try:
            async with session.get(lastfm_url, timeout=3) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    log.info("Fetched album art from Last.fm")
                    return content
                else:
                    log.debug("Last.fm returned status %s", resp.status)
        except asyncio.TimeoutError:
            log.warning("Timeout fetching from Last.fm URL")
        except Exception as e:
            log.exception("Error fetching from Last.fm: %s", e)
        return None

    # Try Last.fm first
    lastfm_bytes = await fetch_lastfm_art(lastfm_url)
    if lastfm_bytes:
        return lastfm_bytes

    # Try MusicBrainz/CAA
    def mbid_search():
        try:
            result = musicbrainzngs.search_releases(
                artist=artist, release=album, limit=1
            )
            if "release-list" in result and result["release-list"]:
                mbid = result["release-list"][0]["id"]
                log.debug("Found MBID for %s / %s: %s", artist, album, mbid)
                return mbid
            else:
                log.debug("No MusicBrainz results for %s / %s", artist, album)
        except Exception as e:
            log.exception("MusicBrainz search failed for %s / %s: %s", artist, album, e)
        return None

    try:
        mbid = await loop.run_in_executor(None, mbid_search)
    except Exception as e:
        log.exception("Error searching MusicBrainz: %s", e)
        mbid = None

    if mbid:
        caa_bytes = await fetch_caa_for_mbid(mbid)
        if caa_bytes:
            return caa_bytes

    log.warning("No album artwork found for %s / %s", artist, album)
    return None


async def fetch_avatar_bytes(session, url):
    try:
        async with session.get(url, timeout=3) as resp:
            if resp.status == 200:
                content = await resp.read()
                log.debug("Successfully fetched avatar")
                return content
            else:
                log.warning("Avatar fetch returned status %s", resp.status)
    except asyncio.TimeoutError:
        log.warning("Timeout fetching avatar from %s", url)
    except Exception as e:
        log.exception("Error fetching avatar: %s", e)
