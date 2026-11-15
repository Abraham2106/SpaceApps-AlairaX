"""OpenAerialMap drone images: footprints from a recorded /meta answer, credits and filtering."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.main import create_app
from backend.app.infrastructure import drones as oam
from backend.app.infrastructure.imagery import ImageryUpstreamError

# Recorded 15 Nov 2026 for the Guanacaste box; contact e-mails and uploader ids removed.
RECORDED = Path(__file__).parent / 'snapshots' / 'oam_meta_guanacaste_2026-11-15.json'
# A view of a few hundred metres around the Filadelfia images.
FILADELFIA = {'west': -85.5535, 'south': 10.4472, 'east': -85.5510, 'north': 10.4490}
FILADELFIA_COG = ('https://oin-hotosm-temp.s3.us-east-1.amazonaws.com/6848b72a064c0ea430648d3e/0/'
                  '6848b72a064c0ea430648d3f.tif')


class FakeMeta:
    def __init__(self, body=None):
        self.calls = []
        self.body = body if body is not None else json.loads(RECORDED.read_bytes())

    def __call__(self, url):
        self.calls.append(url)
        return self.body


def client(drones):
    return TestClient(create_app(drones=drones))


def test_filadelfia_view_lists_its_drone_images_with_date_and_author():
    meta = FakeMeta()
    response = client(oam.OamDrones(fetch=meta)).get('/imagery/drones', params=FILADELFIA)
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == '*'
    body = response.json()
    assert body['catalog'] == 'OpenAerialMap'
    assert body['license'] == 'CC-BY 4.0'
    assert [image['id'] for image in body['images']] == ['6848b842064c0ea430648e5e', '6848ba3b064c0ea430649060']
    first = body['images'][0]
    assert first['date'] == '2025-06-10'
    assert first['provider'] == 'CAOBA REAL ESTATE MEDIA'
    assert first['license'] == 'CC-BY 4.0'
    assert first['platform'] == 'uav'
    assert first['gsd_m'] == pytest.approx(0.0247, abs=1e-4)
    assert first['tiles'] == (
        'https://titiler.hotosm.org/cog/tiles/WebMercatorQuad/{z}/{x}/{y}@1x.png?url='
        'https%3A%2F%2Foin-hotosm-temp.s3.us-east-1.amazonaws.com%2F6848b72a064c0ea430648d3e%2F0%2F'
        '6848b72a064c0ea430648d3f.tif')
    # The whole area is read once; the box only filters.
    assert meta.calls == ['https://api.openaerialmap.org/meta?bbox=-86.2%2C9.4%2C-84.4%2C11.4&limit=100']


def test_no_personal_contact_reaches_the_page():
    body = client(oam.OamDrones(fetch=FakeMeta())).get(
        '/imagery/drones', params={'west': -86.2, 'south': 9.4, 'east': -84.4, 'north': 11.4}).json()
    assert len(body['images']) == 5
    text = json.dumps(body)
    assert '@' not in text.replace('{y}@1x', '')
    assert all('contact' not in image and 'user' not in image for image in body['images'])


def test_view_outside_every_footprint_lists_nothing():
    # Liberia centre: no drone image there.
    body = client(oam.OamDrones(fetch=FakeMeta())).get(
        '/imagery/drones', params={'west': -85.45, 'south': 10.62, 'east': -85.43, 'north': 10.64}).json()
    assert body['images'] == []


def test_catalog_is_cached_between_views():
    meta = FakeMeta()
    api = client(oam.OamDrones(fetch=meta))
    api.get('/imagery/drones', params=FILADELFIA)
    api.get('/imagery/drones', params={'west': -85.2, 'south': 9.6, 'east': -85.1, 'north': 9.7})
    assert len(meta.calls) == 1


def test_cache_expires_after_an_hour():
    now = [0.0]
    meta = FakeMeta()
    drones = oam.OamDrones(fetch=meta, clock=lambda: now[0])
    drones.search(**FILADELFIA)
    now[0] = oam.CACHE_SECONDS + 1
    drones.search(**FILADELFIA)
    assert len(meta.calls) == 2


def test_images_from_unknown_hosts_or_without_provider_are_left_out():
    record = json.loads(RECORDED.read_bytes())['results'][0]
    assert oam.image_summary(record)['tiles'].endswith(oam.quote(FILADELFIA_COG, safe=''))
    assert oam.image_summary({**record, 'uuid': 'https://evil.example.com/a.tif'}) is None
    assert oam.image_summary({**record, 'uuid': 'http://oin-hotosm-temp.s3.amazonaws.com/a.tif'}) is None
    assert oam.image_summary({**record, 'provider': ''}) is None
    assert oam.image_summary({**record, 'bbox': [1, 2, 3]}) is None


@pytest.mark.parametrize('params', [
    {'west': -85.0, 'south': 10.0, 'east': -85.1, 'north': 10.1},   # west of east
    {'west': -80.0, 'south': 10.0, 'east': -79.0, 'north': 11.0},   # outside Guanacaste
    {'west': -85.0, 'south': 10.0, 'east': -84.9},                  # missing north
])
def test_bad_boxes_are_refused_without_calling_oam(params):
    meta = FakeMeta()
    response = client(oam.OamDrones(fetch=meta)).get('/imagery/drones', params=params)
    assert response.status_code == 422
    assert meta.calls == []


def test_oam_outage_is_a_502_with_open_cors():
    def down(url):
        raise ImageryUpstreamError('OpenAerialMap is unreachable')
    response = client(oam.OamDrones(fetch=down)).get('/imagery/drones', params=FILADELFIA)
    assert response.status_code == 502
    assert response.headers['access-control-allow-origin'] == '*'


def test_unexpected_answer_is_a_502():
    response = client(oam.OamDrones(fetch=FakeMeta({'oops': 1}))).get('/imagery/drones', params=FILADELFIA)
    assert response.status_code == 502
