"""Destination imagery and descriptions from the Wikipedia REST API.

Only real images published on Wikimedia Commons are returned. If the lookup
fails the frontend falls back to a designed gradient instead of a stock or
invented picture.
"""

from __future__ import annotations

import logging
import re
import threading
from urllib.parse import quote

from app.config import get_settings
from app.utils.http import ExternalAPIError, get_json

logger = logging.getLogger(__name__)

_CACHE: dict[str, dict] = {}
_LOCK = threading.Lock()

WIKI_TITLES = {"goa": "Goa", "bangalore": "Bangalore", "delhi": "Delhi"}


def _resize(url: str | None, width: int = 1280) -> str | None:
    if not url:
        return None
    url = url.split("?")[0]
    # Thumbnail URLs look like .../thumb/a/ab/File.jpg/330px-File.jpg
    return re.sub(r"/(\d+)px-", f"/{width}px-", url)


def get_destination_profile(city: str) -> dict:
    """Return ``{city, description, extract, image_url, image_credit}``."""
    key = city.lower()
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
    settings = get_settings()
    title = WIKI_TITLES.get(key, city)
    profile = {
        "city": city,
        "description": None,
        "extract": None,
        "image_url": None,
        "image_credit": None,
        "source_url": None,
    }
    try:
        payload = get_json(settings.wikipedia_summary_url + quote(title))
        thumb = (payload.get("thumbnail") or {}).get("source")
        original = (payload.get("originalimage") or {}).get("source")
        image = _resize(thumb) if thumb and "/thumb/" in thumb else original
        profile.update({
            "description": payload.get("description"),
            "extract": payload.get("extract"),
            "image_url": image.split("?")[0] if image else None,
            "image_credit": "Wikimedia Commons via Wikipedia" if image else None,
            "source_url": (payload.get("content_urls") or {})
            .get("desktop", {}).get("page"),
        })
    except ExternalAPIError as exc:
        logger.warning("Destination profile lookup failed for %s: %s", city, exc)
        return profile  # do not cache failures
    with _LOCK:
        _CACHE[key] = profile
    return profile
