"""Drone images of Guanacaste from the public OpenAerialMap catalog.

OpenAerialMap (OAM) only allows its own map to call ``/meta`` from a browser, so the
footprints are read here and handed to the page. Tiles are not proxied: titiler.hotosm.org
cuts them from each image's COG and answers with open CORS. Every image keeps its own
date, resolution, provider and licence, so the page can credit the author by name.
Contact e-mails and uploader ids are dropped: they are personal data, not credits.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import quote, urlencode, urlparse

from backend.app.infrastructure.imagery import (
    AREA, USER_AGENT, ImageryInputError, ImageryUpstreamError,
)

META_URL = 'https://api.openaerialmap.org/meta'
TILER = 'https://titiler.hotosm.org/cog/tiles/WebMercatorQuad/{z}/{x}/{y}@1x.png'
CATALOG = 'OpenAerialMap'
# Only COGs from the OAM bucket are passed to the tiler; any other host is left out.
ALLOWED_COG_HOSTS = frozenset({
    'oin-hotosm-temp.s3.amazonaws.com',
    'oin-hotosm-temp.s3.us-east-1.amazonaws.com',
})
LIMIT = 100
CACHE_SECONDS = 3600

FetchJson = Callable[[str], dict]


def fetch_oam_json(url: str, timeout: float = 20) -> dict:
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise ImageryUpstreamError(f'OpenAerialMap answered {error.code}') from error
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise ImageryUpstreamError('OpenAerialMap is unreachable') from error


def check_box(west: float, south: float, east: float, north: float) -> tuple[float, float, float, float]:
    if not (west < east and south < north):
        raise ImageryInputError('The box must go west to east and south to north')
    w, s, e, n = AREA
    if east < w or west > e or north < s or south > n:
        raise ImageryInputError('The box is outside Guanacaste')
    return west, south, east, north


def tile_template(cog: str) -> str | None:
    parsed = urlparse(cog)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_COG_HOSTS or not parsed.path.endswith('.tif'):
        return None
    return f'{TILER}?url={quote(cog, safe="")}'


def image_summary(result: dict) -> dict | None:
    """One OAM record as the page needs it, or None when it cannot be shown or credited."""
    try:
        props = result.get('properties') or {}
        bbox = [float(v) for v in result['bbox']]
        acquired = str(result['acquisition_start'])
        gsd = result.get('gsd', props.get('resolution_in_meters'))
        tiles = tile_template(str(result['uuid']))
        provider = str(result.get('provider') or '').strip()
    except (KeyError, TypeError, ValueError):
        return None
    if len(bbox) != 4 or not tiles or not provider or len(acquired) < 10:
        return None
    return {
        'id': str(result['_id']),
        'title': str(result.get('title') or ''),
        'date': acquired[:10],
        'datetime': acquired,
        'gsd_m': float(gsd) if isinstance(gsd, (int, float)) else None,
        'provider': provider,
        'platform': result.get('platform'),
        'sensor': props.get('sensor'),
        'license': str(props.get('license') or ''),
        'bbox': bbox,
        'tiles': tiles,
    }


def intersects(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> bool:
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


class OamDrones:
    """Reads every OAM image of the area once an hour and filters by box locally."""

    def __init__(self, fetch: FetchJson = fetch_oam_json, clock: Callable[[], float] = time.monotonic):
        self.fetch = fetch
        self.clock = clock
        self.lock = threading.Lock()
        self.cached: tuple[float, list[dict], str] | None = None

    def catalog(self) -> tuple[list[dict], str]:
        with self.lock:
            if self.cached and self.clock() - self.cached[0] < CACHE_SECONDS:
                return self.cached[1], self.cached[2]
        query = urlencode({'bbox': ','.join(str(v) for v in AREA), 'limit': LIMIT})
        body = self.fetch(f'{META_URL}?{query}')
        if not isinstance(body, dict) or not isinstance(body.get('results'), list):
            raise ImageryUpstreamError('OpenAerialMap sent an unexpected answer')
        images = [image for image in map(image_summary, body['results']) if image]
        # Most recent first, then sharpest: the page shows the first one under the view centre.
        images.sort(key=lambda image: (image['datetime'], -(image['gsd_m'] or 1e9)), reverse=True)
        license_ = str((body.get('meta') or {}).get('license') or 'CC-BY 4.0')
        with self.lock:
            self.cached = (self.clock(), images, license_)
        return images, license_

    def search(self, west: float, south: float, east: float, north: float) -> dict:
        box = check_box(west, south, east, north)
        images, license_ = self.catalog()
        return {
            'catalog': CATALOG,
            'license': license_,
            'images': [image for image in images if intersects(image['bbox'], box)],
        }
