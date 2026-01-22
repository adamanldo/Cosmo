import logging
from io import BytesIO

from PIL import Image

log = logging.getLogger(__name__)


def validate_image_bytes(data):
    try:
        bio = BytesIO(data)
        with Image.open(bio) as img:
            img.verify()
        return True
    except Exception as e:
        log.warning("Image validation failed: %s", e)
        return False


def decode_image_from_bytes(data):
    try:
        bio = BytesIO(data)
        with Image.open(bio) as img:
            img.load()
            output = BytesIO()
            img.save(output, format="PNG")
            output.seek(0)
            log.debug("Successfully decoded and converted image to PNG BytesIO")
            return output
    except Exception as e:
        log.exception("Failed to decode image from bytes: %s", e)
        raise
