"""Sentinel-2 imagery: scene choice from a recorded Earth Search answer, tile cache and PNG."""

import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.api.main import create_app
from backend.app.infrastructure import imagery as s2

RECORDED = Path(__file__).parent / 'snapshots' / 'earth_search_liberia_2026-11-08.json'
TODAY = date(2026, 11, 15)
LIBERIA = {'lon': -85.44, 'lat': 10.63}
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
HREF = ('https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/16/P/FS/'
        '2026/10/S2B_16PFS_20261024_0_L2A/TCI.tif')


class FakeCatalog:
    def __init__(self, item_href=HREF):
        self.calls = []
        self.item_href = item_href

    def __call__(self, url, body):
        self.calls.append((url, body))
        if url.endswith('/search'):
            return json.loads(RECORDED.read_bytes())
        scene_id = url.rsplit('/', 1)[-1]
        return {'id': scene_id, 'assets': {'visual': {'href': self.item_href}}}


class FakeRender:
    def __init__(self, result=PNG_MAGIC + b'tile'):
        self.calls = []
        self.result = result

    def __call__(self, href, z, x, y):
        self.calls.append((href, z, x, y))
        return self.result


def service(catalog=None, render=None):
    return s2.SentinelImagery(fetch=catalog or FakeCatalog(), render=render or FakeRender(),
                              today=lambda: TODAY)


def client(sentinel):
    return TestClient(create_app(imagery=sentinel))


def test_search_picks_least_cloudy_scene_in_window():
    catalog = FakeCatalog()
    response = client(service(catalog)).get('/imagery/search', params={'date': '2026-11-08', **LIBERIA})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == '*'
    body = response.json()
    # 2026-10-24 has 14.2 % cloud; 2026-10-29 has 19.5 %; the November scenes are overcast.
    assert body['scene']['id'] == 'S2B_16PFS_20261024_0_L2A'
    assert body['scene']['date'] == '2026-10-24'
    assert body['scene']['cloud_cover'] == 14.2
    assert body['scene']['platform'] == 'sentinel-2b'
    assert body['provider'] == 'Copernicus Sentinel-2 L2A'
    assert body['resolution_m'] == 10
    assert body['attribution'] == 'Contains modified Copernicus Sentinel data 2026'
    assert body['window'] == {'start': '2026-10-24', 'end': '2026-11-08'}
    assert (body['minzoom'], body['maxzoom']) == (9, 14)
    sent = catalog.calls[0][1]
    assert sent['collections'] == ['sentinel-2-l2a']
    assert sent['intersects']['coordinates'] == [-85.44, 10.63]
    assert sent['datetime'] == '2026-10-24T00:00:00Z/2026-11-08T23:59:59Z'


def test_search_is_cached_for_nearby_points():
    catalog = FakeCatalog()
    api = client(service(catalog))
    api.get('/imagery/search', params={'date': '2026-11-08', **LIBERIA})
    api.get('/imagery/search', params={'date': '2026-11-08', 'lon': -85.4401, 'lat': 10.6302})
    assert len(catalog.calls) == 1


def test_overcast_window_returns_no_scene_instead_of_a_cloudy_one():
    features = [f for f in json.loads(RECORDED.read_bytes())['features']
                if f['properties']['eo:cloud_cover'] > 80]
    scene = s2.pick_scene(features, date(2026, 11, 8))
    assert scene is None
    sentinel = s2.SentinelImagery(fetch=lambda url, body: {'features': features},
                                  render=FakeRender(), today=lambda: TODAY)
    body = sentinel.search('2026-11-08', **LIBERIA)
    assert body['scene'] is None and body['reason'] == 'no_clear_scene' and body['attribution'] is None


def test_ties_go_to_the_scene_nearest_the_requested_day():
    def feature(scene_id, day):
        return {'id': scene_id, 'bbox': [0, 0, 1, 1],
                'properties': {'datetime': f'{day}T16:20:00Z', 'eo:cloud_cover': 5.0}}
    picked = s2.pick_scene([feature('S2A_16PFS_20261001_0_L2A', '2026-10-01'),
                            feature('S2B_16PFS_20261010_0_L2A', '2026-10-10')], date(2026, 10, 12))
    assert picked['id'] == 'S2B_16PFS_20261010_0_L2A'


@pytest.mark.parametrize('params', [
    {'date': '2026-11-16', **LIBERIA},            # future
    {'date': '2014-01-01', **LIBERIA},            # before Sentinel-2
    {'date': '2026-2-1', **LIBERIA},              # not ISO
    {'date': '2026-11-08', 'lon': -80.0, 'lat': 10.0},  # outside Guanacaste
])
def test_search_rejects_bad_requests(params):
    catalog = FakeCatalog()
    response = client(service(catalog)).get('/imagery/search', params=params)
    assert response.status_code == 422
    assert response.headers['access-control-allow-origin'] == '*'
    assert catalog.calls == []


def test_catalog_outage_is_a_502():
    def down(url, body):
        raise s2.ImageryUpstreamError('Earth Search is unreachable')
    response = client(service(down)).get('/imagery/search', params={'date': '2026-11-08', **LIBERIA})
    assert response.status_code == 502


def test_tile_is_png_and_cached():
    catalog, render = FakeCatalog(), FakeRender()
    api = client(service(catalog, render))
    path = '/imagery/tiles/S2B_16PFS_20261024_0_L2A/11/537/963'
    first = api.get(path)
    second = api.get(path)
    assert first.status_code == second.status_code == 200
    assert first.headers['content-type'] == 'image/png'
    assert first.content.startswith(PNG_MAGIC)
    assert first.headers['access-control-allow-origin'] == '*'
    assert render.calls == [(HREF, 11, 537, 963)]
    assert len([c for c in catalog.calls if '/items/' in c[0]]) == 1


def test_tile_outside_scene_is_204_and_remembered():
    render = FakeRender(result=None)
    api = client(service(render=render))
    path = '/imagery/tiles/S2B_16PFS_20261024_0_L2A/12/1000/1000'
    assert api.get(path).status_code == 204
    assert api.get(path).status_code == 204
    assert len(render.calls) == 1


@pytest.mark.parametrize('path', [
    '/imagery/tiles/S2B_16PFS_20261024_0_L2A/8/67/117',     # below zoom 9
    '/imagery/tiles/S2B_16PFS_20261024_0_L2A/15/1/1',       # above zoom 14
    '/imagery/tiles/S2B_16PFS_20261024_0_L2A/11/4096/1',    # x out of range
    '/imagery/tiles/LC09_016053_20261024/11/537/963',       # not a Sentinel-2 id
])
def test_tile_rejects_bad_requests(path):
    render = FakeRender()
    assert client(service(render=render)).get(path).status_code == 422
    assert render.calls == []


def test_asset_outside_public_bucket_is_refused():
    catalog = FakeCatalog(item_href='https://evil.example.com/TCI.tif')
    render = FakeRender()
    response = client(service(catalog, render)).get('/imagery/tiles/S2B_16PFS_20261024_0_L2A/11/537/963')
    assert response.status_code == 502
    assert render.calls == []


def test_lru_drops_oldest():
    cache = s2.LruBytes(2)
    cache.put('a', b'1')
    cache.put('b', b'2')
    cache.get('a')
    cache.put('c', b'3')
    assert cache.get('b') is None and cache.get('a') == b'1' and len(cache) == 2


def test_render_cuts_a_real_png_from_a_local_cog(tmp_path):
    rasterio = pytest.importorskip('rasterio')
    from rasterio.transform import from_bounds

    # Web-mercator bounds of tile z11/537/963 (over Liberia), 256 px RGB, nodata 0.
    z, x, y = 11, 537, 963
    size = 2 * 20037508.342789244 / 2 ** z
    west = -20037508.342789244 + x * size
    north = 20037508.342789244 - y * size
    path = tmp_path / 'tci.tif'
    data = np.full((3, 256, 256), 120, dtype='uint8')
    with rasterio.open(path, 'w', driver='GTiff', width=256, height=256, count=3, dtype='uint8',
                       crs='EPSG:3857', nodata=0,
                       transform=from_bounds(west, north - size, west + size, north, 256, 256)) as dst:
        dst.write(data)
    png = s2.render_cog_tile(str(path), z, x, y)
    assert png is not None and png.startswith(PNG_MAGIC)
    assert s2.render_cog_tile(str(path), z, x + 50, y) is None
