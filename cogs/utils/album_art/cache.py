import logging
import os

from diskcache import Cache

log = logging.getLogger(__name__)


class AlbumCache:
    def __init__(self, path, size_limit: int = 2 * 1024**3):
        try:
            os.makedirs(path, exist_ok=True)
            self._cache = Cache(path, size_limit=size_limit)
            log.info(
                "Initialized album cache at %s with size limit %s bytes",
                path,
                size_limit,
            )
        except Exception as e:
            log.exception("Failed to initialize album cache: %s", e)
            raise

    def get(self, key):
        try:
            value = self._cache.get(key, default=None)
            return value
        except Exception as e:
            log.exception("Error retrieving from cache for key %s: %s", key, e)
            return None

    def set(self, key, value):
        try:
            self._cache.set(key, value)
        except Exception as e:
            log.exception("Error setting cache for key %s: %s", key, e)

    def delete(self, key: str):
        try:
            if key in self._cache:
                del self._cache[key]
        except Exception as e:
            log.exception("Error deleting cache entry for key %s: %s", key, e)

    def close(self):
        try:
            self._cache.close()
        except Exception as e:
            log.debug("Error closing cache: %s", e)
