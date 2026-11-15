"""Sentinel-2 L2A scenes from the public Earth Search STAC catalog, served as web tiles.

Earth Search (Element 84) indexes the Copernicus Sentinel-2 L2A archive held in the
AWS Open Data bucket ``sentinel-cogs``. Searching is free and needs no key. Tiles are
cut from the scene's true-colour COG (TCI, 10 m) with rio-tiler. One scene is chosen
per request, so every tile on screen comes from the same day and the same scene id.
"""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from collections import OrderedDict
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

STAC_ROOT = 'https://earth-search.aws.element84.com/v1'
COLLECTION = 'sentinel-2-l2a'
USER_AGENT = 'NandaView/0.1 (NASA Space Apps climate research)'
# Only COGs from the public Sentinel-2 bucket are read; any other host is refused.
ALLOWED_ASSET_HOSTS = frozenset({'sentinel-cogs.s3.us-west-2.amazonaws.com'})
PROVIDER = 'Copernicus Sentinel-2 L2A'
CATALOG = 'Earth Search (Element 84) · AWS Open Data'
RESOLUTION_M = 10
# Guanacaste with a margin. Requests outside it are refused, not served.
AREA = (-86.2, 9.4, -84.4, 11.4)
FIRST_DATE = date(2015, 6, 27)  # first Sentinel-2A acquisition
WINDOW_DAYS = 15
MAX_CLOUD = 60.0
MIN_ZOOM, MAX_ZOOM = 9, 14
SCENE_ID = re.compile(r'^S2[A-D]_\d{2}[A-Z]{3}_\d{8}_\d+_L2A$')

FetchJson = Callable[[str, dict | None], dict]
RenderTile = Callable[[str, int, int, int], bytes | None]


class ImageryInputError(ValueError):
    """The request cannot be served: bad date, place, zoom or scene id."""


class ImageryUpstreamError(RuntimeError):
    """Earth Search or the COG bucket did not answer as expected."""


def attribution(year: int) -> str:
    return f'Contains modified Copernicus Sentinel data {year}'


def fetch_json(url: str, body: dict | None = None, timeout: float = 20) -> dict:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, headers={
        'User-Agent': USER_AGENT,
        'Accept': 'application/geo+json, application/json',
        **({'Content-Type': 'application/json'} if data else {}),
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise ImageryInputError('Scene not found in the catalog') from error
        raise ImageryUpstreamError(f'Earth Search answered {error.code}') from error
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise ImageryUpstreamError('Earth Search is unreachable') from error


def render_cog_tile(href: str, z: int, x: int, y: int) -> bytes | None:
    """Cut one 256 px PNG tile from a COG. Returns None when the tile is outside it."""
    import rasterio
    from rio_tiler.errors import TileOutsideBounds
    from rio_tiler.io import Reader

    env = {
        'GDAL_DISABLE_READDIR_ON_OPEN': 'EMPTY_DIR',
        'CPL_VSIL_CURL_ALLOWED_EXTENSIONS': '.tif',
        'GDAL_HTTP_MERGE_CONSECUTIVE_RANGES': 'YES',
        'GDAL_HTTP_MULTIPLEX': 'YES',
        'GDAL_HTTP_USERAGENT': USER_AGENT,
        'VSI_CACHE': 'TRUE',
        'AWS_NO_SIGN_REQUEST': 'YES',
    }
    try:
        with rasterio.Env(**env), Reader(href) as cog:
            image = cog.tile(x, y, z, tilesize=256)
    except TileOutsideBounds:
        return None
    except Exception as error:  # GDAL raises several unrelated types on network trouble
        raise ImageryUpstreamError('Cannot read the Sentinel-2 COG') from error
    return image.render(img_format='PNG')


def parse_day(value: str, today: date) -> date:
    try:
        day = date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ImageryInputError('date must be YYYY-MM-DD') from error
    if value != day.isoformat():
        raise ImageryInputError('date must be YYYY-MM-DD')
    if day < FIRST_DATE or day > today:
        raise ImageryInputError(f'date must be between {FIRST_DATE} and {today}')
    return day


def check_place(lon: float, lat: float) -> None:
    west, south, east, north = AREA
    if not (west <= lon <= east and south <= lat <= north):
        raise ImageryInputError('point is outside the Guanacaste study area')


def check_tile(z: int, x: int, y: int) -> None:
    if not MIN_ZOOM <= z <= MAX_ZOOM:
        raise ImageryInputError(f'zoom must be between {MIN_ZOOM} and {MAX_ZOOM}')
    if not (0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise ImageryInputError('tile index out of range')


def check_scene_id(scene_id: str) -> None:
    if not SCENE_ID.match(scene_id):
        raise ImageryInputError('not a Sentinel-2 L2A scene id')


def scene_summary(feature: dict) -> dict | None:
    """Keep the fields the badge needs. Returns None for an item that cannot be cited."""
    props = feature.get('properties') or {}
    stamp = props.get('datetime')
    cloud = props.get('eo:cloud_cover')
    bbox = feature.get('bbox')
    scene_id = feature.get('id')
    if not (isinstance(scene_id, str) and SCENE_ID.match(scene_id) and isinstance(stamp, str)):
        return None
    if not (isinstance(bbox, list) and len(bbox) == 4):
        return None
    try:
        moment = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    except ValueError:
        return None
    return {
        'id': scene_id,
        'datetime': moment.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'date': moment.astimezone(timezone.utc).date().isoformat(),
        'cloud_cover': round(float(cloud), 1) if isinstance(cloud, (int, float)) else None,
        'platform': props.get('platform'),
        'bbox': [float(value) for value in bbox],
    }


def pick_scene(features: list[dict], requested: date) -> dict | None:
    """Least cloudy scene under MAX_CLOUD; ties go to the one nearest the requested day."""
    scenes = [scene for scene in map(scene_summary, features) if scene]
    usable = [scene for scene in scenes
              if scene['cloud_cover'] is not None and scene['cloud_cover'] <= MAX_CLOUD]
    if not usable:
        return None

    def rank(scene: dict):
        gap = abs((date.fromisoformat(scene['date']) - requested).days)
        return (scene['cloud_cover'], gap, scene['id'])

    return min(usable, key=rank)


def asset_href(item: dict) -> str:
    href = ((item.get('assets') or {}).get('visual') or {}).get('href')
    if not isinstance(href, str):
        raise ImageryUpstreamError('Scene has no true-colour asset')
    parsed = urlparse(href)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_ASSET_HOSTS:
        raise ImageryUpstreamError('Scene asset is not in the public Sentinel-2 bucket')
    if not parsed.path.endswith('.tif'):
        raise ImageryUpstreamError('Scene asset is not a GeoTIFF')
    return href


class LruBytes:
    """Small thread-safe LRU for rendered tiles and scene lookups."""

    def __init__(self, size: int):
        self.size = size
        self.items: OrderedDict = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            if key not in self.items:
                return None
            self.items.move_to_end(key)
            return self.items[key]

    def put(self, key, value) -> None:
        with self.lock:
            self.items[key] = value
            self.items.move_to_end(key)
            while len(self.items) > self.size:
                self.items.popitem(last=False)

    def __len__(self) -> int:
        return len(self.items)


class SentinelImagery:
    def __init__(self, fetch: FetchJson = fetch_json, render: RenderTile = render_cog_tile,
                 today: Callable[[], date] = lambda: datetime.now(timezone.utc).date(),
                 tile_cache_size: int = 512):
        self.fetch = fetch
        self.render = render
        self.today = today
        self.tiles = LruBytes(tile_cache_size)
        self.hrefs = LruBytes(64)
        self.searches = LruBytes(128)

    def search(self, day: str, lon: float, lat: float) -> dict:
        requested = parse_day(day, self.today())
        check_place(lon, lat)
        # About 1 km of rounding, so nearby pans reuse the same answer.
        key = (requested.isoformat(), round(lon, 2), round(lat, 2))
        cached = self.searches.get(key)
        if cached is not None:
            return cached
        start = max(FIRST_DATE, requested - timedelta(days=WINDOW_DAYS))
        body = {
            'collections': [COLLECTION],
            'intersects': {'type': 'Point', 'coordinates': [lon, lat]},
            'datetime': f'{start.isoformat()}T00:00:00Z/{requested.isoformat()}T23:59:59Z',
            'limit': 50,
            'fields': {
                'include': ['id', 'bbox', 'properties.datetime', 'properties.eo:cloud_cover',
                            'properties.platform'],
                'exclude': ['geometry', 'links', 'assets'],
            },
        }
        document = self.fetch(f'{STAC_ROOT}/search', body)
        features = document.get('features')
        if not isinstance(features, list):
            raise ImageryUpstreamError('Earth Search returned no feature list')
        scene = pick_scene(features, requested)
        result = {
            'provider': PROVIDER,
            'catalog': CATALOG,
            'resolution_m': RESOLUTION_M,
            'requested_date': requested.isoformat(),
            'window': {'start': start.isoformat(), 'end': requested.isoformat()},
            'max_cloud_cover': MAX_CLOUD,
            'minzoom': MIN_ZOOM,
            'maxzoom': MAX_ZOOM,
            'scene': scene,
            'reason': None if scene else 'no_clear_scene',
            'attribution': attribution(int(scene['date'][:4])) if scene else None,
        }
        self.searches.put(key, result)
        return result

    def href_for(self, scene_id: str) -> str:
        check_scene_id(scene_id)
        href = self.hrefs.get(scene_id)
        if href is None:
            item = self.fetch(f'{STAC_ROOT}/collections/{COLLECTION}/items/{scene_id}', None)
            if item.get('id') != scene_id:
                raise ImageryUpstreamError('Catalog returned a different scene')
            href = asset_href(item)
            self.hrefs.put(scene_id, href)
        return href

    def tile(self, scene_id: str, z: int, x: int, y: int) -> bytes | None:
        check_scene_id(scene_id)
        check_tile(z, x, y)
        key = (scene_id, z, x, y)
        cached = self.tiles.get(key)
        if cached is not None:
            return cached or None
        png = self.render(self.href_for(scene_id), z, x, y)
        # An empty value remembers "outside the scene" so it is not asked again.
        self.tiles.put(key, png or b'')
        return png
