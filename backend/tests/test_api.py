"""HTTP contract, comparison matrix, and release data for the Pages demo."""

import json
from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.api.main import app, create_app
from backend.app.api.schemas.contracts import CompareRequest, CompareResponse
from backend.app.simulation.version import MODEL_VERSION
from backend.tests.test_kernel import _mock_inputs
from scripts.export_contracts import ROTATIONS, SCENARIOS, ZONE, export

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def prepared_api(tmp_path):
    years = (2015, 2023)
    inputs = _mock_inputs(years)
    catalog = {
        '_mock': True, 'zona': ZONE.model_dump(), 'scenarios': {
            scenario: {'status': 'available', '_mock': True, 'k': len(years),
                       'neighbors': [{'year': year, 'distance': rank / 10}
                                     for rank, year in enumerate(years, 1)]}
            for scenario in SCENARIOS
        },
    }
    path = tmp_path / 'analogs.json'
    path.write_text(json.dumps(catalog), encoding='utf-8')
    for scenario in SCENARIOS:
        batch = [item.model_copy(update={'scenario_id': scenario})
                 .model_dump(mode='json', by_alias=True) for item in inputs]
        (tmp_path / f'{scenario}.json').write_text(json.dumps(batch), encoding='utf-8')
    return TestClient(create_app(path, tmp_path, allow_mock=True)), path


def request_for(scenario='neutral', **updates):
    payload = CompareRequest(zona=ZONE, scenario_id='neutral', k=2).model_dump(mode='json')
    return payload | {'scenario_id': scenario} | updates


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_comparison_matrix(prepared_api, scenario):
    client, _ = prepared_api
    response = client.post('/compare', json=request_for(scenario))
    assert response.status_code == 200, response.text
    assert response.json()['_mock'] is True
    comparison = CompareResponse.model_validate(response.json())
    assert comparison.scenario_id == scenario
    assert comparison.warnings[0].startswith('SYNTHETIC MOCK')
    assert tuple(rotation.rotation_id for rotation in comparison.rotations) == ROTATIONS
    for rotation in comparison.rotations:
        assert len(rotation.runs) == 2
        for run in rotation.runs:
            assert run.mock and run.model_version == MODEL_VERSION
            assert len(run.daily_balance) == 275
            assert run.metrics.crop_water_demand_mm > 0


def test_subset_k_and_baseline(prepared_api):
    client, _ = prepared_api
    response = client.post('/compare', json=request_for(
        k=1, rotation_ids=['rice_legume', 'rice_sorghum'], baseline_rotation_id='rice_sorghum'))
    assert response.status_code == 200, response.text
    result = CompareResponse.model_validate(response.json())
    assert result.baseline_rotation_id == 'rice_sorghum'
    assert [r.rotation_id for r in result.rotations] == ['rice_legume', 'rice_sorghum']
    assert [a.year for a in result.analog_years] == [2015]


def test_missing_data_and_bad_requests(prepared_api):
    client, path = prepared_api
    assert client.post('/compare', json=request_for('unknown')).status_code == 422
    assert client.post('/compare', json=request_for(k=3)).status_code == 409
    unknown_zone = ZONE.model_dump() | {'id': 'unknown'}
    assert client.post('/compare', json=request_for(zona=unknown_zone)).status_code == 404

    batch = path.parent / 'neutral.json'
    batch.unlink()
    missing = client.post('/compare', json=request_for())
    assert missing.status_code == 503
    assert 'Prepared input batch' in missing.json()['detail']
    batch.write_text('[]', encoding='utf-8')
    assert client.post('/compare', json=request_for()).status_code == 409

    blocked = TestClient(create_app(path, path.parent)).post('/compare', json=request_for())
    assert blocked.status_code == 503
    assert 'Synthetic' in blocked.json()['detail']


def test_repository_catalog():
    client = TestClient(app)
    assert client.get('/health').json()['status'] == 'ok'
    rotations = client.get('/rotations').json()['rotations']
    assert {rotation['rotation_id'] for rotation in rotations} == set(ROTATIONS)
    sources = client.get('/sources')
    assert sources.status_code == 200 and sources.json()['source_refs']
    catalog = client.get('/scenarios').json()
    assert catalog['_mock'] is False
    assert set(catalog['scenarios']) == set(SCENARIOS)
    for scenario, entry in catalog['scenarios'].items():
        if entry['status'] == 'unavailable':
            response = client.post('/compare', json=request_for(scenario, zona=catalog['zona']))
            assert response.status_code == 409
            assert response.json()['detail'] == entry['reason']


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_published_data_matrix(scenario):
    data = ROOT / 'frontend' / 'public' / 'data'
    result = CompareResponse.model_validate_json((data / f'compare-{scenario}.json').read_bytes())
    assert result.scenario_id == scenario
    assert {rotation.rotation_id for rotation in result.rotations} == set(ROTATIONS)
    if result.mock:
        assert any('SYNTHETIC MOCK' in warning for warning in result.warnings)


def test_pages_placeholder_artifact(tmp_path):
    export(tmp_path)
    dist = tmp_path / 'dist'
    shutil.copytree(tmp_path / 'frontend' / 'public', dist)
    shutil.copyfile(ROOT / '.github' / 'pages-placeholder' / 'index.html', dist / 'index.html')
    (dist / '.nojekyll').touch()
    pages = FastAPI()
    base = '/SpaceApps-AlairaX'
    pages.mount(base, StaticFiles(directory=dist, html=True))
    client = TestClient(pages)
    page = client.get(f'{base}/')
    assert page.status_code == 200 and '_mock: true' in page.text
    rotations = client.get(f'{base}/data/rotations.json')
    scenarios = client.get(f'{base}/data/scenarios.json')
    assert rotations.status_code == scenarios.status_code == 200
    assert rotations.json()['_mock'] is True and scenarios.json()['_mock'] is True
    for scenario in SCENARIOS:
        name = f'compare-{scenario}.json'
        assert name in scenarios.text
        comparison = client.get(f'{base}/data/{name}')
        assert comparison.status_code == 200
        assert CompareResponse.model_validate_json(comparison.content).mock is True
