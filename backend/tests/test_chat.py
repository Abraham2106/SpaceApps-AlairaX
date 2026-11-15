"""Chat grounding, location boundaries and server credential isolation."""

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError

from fastapi.testclient import TestClient
import pytest

from backend.app.api.main import create_app
from backend.app.api.schemas.chat import ChatSelection
from backend.app.application.chat_context import CantonContext, prompt_context
from backend.app.infrastructure.gemini import GeminiClient, GeminiError
from backend.app.application.canton_simulation import CantonSimulationError, CantonSimulator
from backend.app.api.schemas.contracts import CompareResponse


class ClimateCache:
    def __init__(self, missing=False):
        self.urls = []
        self.missing = missing

    def get(self, url, **kwargs):
        self.urls.append(url)
        rain = -999 if self.missing else 2
        payload = {'properties': {'parameter': {
            'PRECTOTCORR': {'20250101': rain, '20250102': -999},
            'T2M_MIN': {'20250101': 22, '20250102': 23},
            'T2M_MAX': {'20250101': 33, '20250102': 34},
            'RH2M': {'20250101': 70, '20250102': 72},
            'WS2M': {'20250101': 2, '20250102': 3},
            'ALLSKY_SFC_SW_DWN': {'20250101': 20, '20250102': 21},
        }}, 'parameters': {name: {'units': unit} for name, unit in {
            'PRECTOTCORR': 'mm/day', 'T2M_MIN': 'C', 'T2M_MAX': 'C',
            'RH2M': '%', 'WS2M': 'm/s', 'ALLSKY_SFC_SW_DWN': 'MJ/m^2/day',
        }.items()}}
        return json.dumps(payload).encode(), {'fetched_at': datetime.now(timezone.utc).isoformat(), 'url': url}


def selection(**kwargs):
    return {'canton_ids': ['canas'], 'start': '2025-01-01', 'end': '2025-01-02', **kwargs}


def test_context_matches_each_point_and_keeps_missing_days():
    cache = ClimateCache()
    context = CantonContext(cache=cache).build(ChatSelection(**selection(canton_ids=['canas', 'liberia'])))
    first, second = context['cantons']
    assert first['latitude'] != second['latitude']
    assert len(set(cache.urls)) == 2
    assert first['status'] == 'partial'
    rain = first['summary']['precipitation_mm']
    assert rain['total'] == 2 and rain['available_days'] == 1 and rain['expected_days'] == 2
    assert rain['complete'] is False
    assert first['daily'][1]['precipitation_mm'] is None
    assert first['summary']['et0_mm']['available_days'] == 2
    assert context['model_scope'] == 'regional_pilot'
    assert first['validated'] is False
    assert 'daily' not in prompt_context(context)['cantons'][0]


def test_guanacaste_catalog_and_unknown_canton():
    service = CantonContext(cache=ClimateCache())
    assert len(service.catalog()) == 11
    assert 'san-jose' not in service.catalog()
    with pytest.raises(ValueError):
        service.build(ChatSelection(**selection(canton_ids=['san-jose'])))


@pytest.mark.parametrize('update', [
    {'canton_ids': []}, {'canton_ids': ['canas', 'canas']},
    {'end': '2024-01-01'}, {'start': '1980-01-01'},
    {'start': '2023-01-01'}, {'end': '2099-01-01'},
])
def test_invalid_selections_rejected(update):
    with pytest.raises(ValueError):
        ChatSelection(**selection(**update))


class Assistant:
    def __init__(self):
        self.payloads = []

    def generate(self, payload):
        self.payloads.append(payload)
        return 'La cobertura de lluvia es parcial. [power:canas]'


def test_chat_passes_server_evidence_and_unverified_history():
    assistant = Assistant()
    client = TestClient(create_app(chat_context=CantonContext(cache=ClimateCache()), gemini=assistant))
    body = {'question': '¿Qué significa?', 'selection': selection(),
            'history': [{'role': 'assistant', 'content': 'Dato previo no verificado'}]}
    response = client.post('/chat', json=body)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['model'] == 'gemini-4-hydrogen'
    assert assistant.payloads[0]['context']['cantons'][0]['id'] == 'canas'
    assert assistant.payloads[0]['history_unverified'] == body['history']
    assert client.post('/chat', json=body | {'temperature': 1}).status_code == 422
    assert client.post('/chat', json=body | {'question': '  '}).status_code == 422


def test_unavailable_data_does_not_call_gemini():
    class Unavailable:
        def build(self, value):
            return {'cantons': [{'id': 'canas', 'status': 'unavailable'}]}
    assistant = Assistant()
    client = TestClient(create_app(chat_context=Unavailable(), gemini=assistant))
    response = client.post('/chat', json={'question': '¿Qué hago?', 'selection': selection()})
    assert response.status_code == 200
    assert 'No hay datos' in response.json()['answer']
    assert assistant.payloads == []


def test_provider_payload_and_secret_redaction(monkeypatch):
    secret = 'fake-test-credential'
    monkeypatch.setenv('GEMINI_API_KEY', secret)
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size):
            return json.dumps({'status': 'completed', 'steps': [
                {'type': 'thought', 'summary': [{'type': 'text', 'text': 'private'}]},
                {'type': 'model_output', 'content': [{'type': 'text', 'text': f'Answer {secret}'}]},
            ]}).encode()
    def send(request, timeout):
        payload = json.loads(request.data)
        assert payload['model'] == 'gemini-4-hydrogen'
        assert payload['generation_config']['thinking_level'] == 'low'
        assert payload['store'] is False
        assert secret not in request.full_url and secret not in request.data.decode()
        assert request.get_header('X-goog-api-key') == secret
        return Response()
    monkeypatch.setattr('backend.app.infrastructure.gemini.urlopen', send)
    text = GeminiClient().generate({'question': 'test'})
    assert secret not in text and 'private' not in text
    assert '[credencial omitida]' in text


def test_provider_errors_do_not_surface_bodies(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-test-secret')
    def send(*args, **kwargs):
        raise HTTPError('https://example.test', 429, 'fake-test-secret', {}, None)
    monkeypatch.setattr('backend.app.infrastructure.gemini.urlopen', send)
    with pytest.raises(GeminiError) as caught:
        GeminiClient().generate({})
    assert caught.value.status == 429
    assert 'fake-test-secret' not in str(caught.value)
    monkeypatch.delenv('GEMINI_API_KEY')
    with pytest.raises(GeminiError) as caught:
        GeminiClient().generate({})
    assert caught.value.status == 503


def test_chat_uses_same_canton_comparison_as_simulator_endpoint():
    class Simulator:
        def __init__(self): self.requests = []
        def point(self, canton_id): return CantonSimulator().point(canton_id)
        def compare(self, canton_id, request, document, inputs_dir):
            self.requests.append((canton_id, request))
            path = Path(__file__).resolve().parents[2] / 'frontend/public/data/compare-neutral.json'
            result = CompareResponse.model_validate_json(path.read_bytes())
            result.zona = request.zona
            for rotation in result.rotations:
                for run in rotation.runs:
                    run.zona = request.zona
            return result
    simulator = Simulator()
    assistant = Assistant()
    client = TestClient(create_app(chat_context=CantonContext(cache=ClimateCache()),
                                   canton_simulator=simulator, gemini=assistant))
    response = client.post('/chat', json={'question': '¿Cuál es el déficit?',
                           'selection': selection(scenario_id='neutral')})
    assert response.status_code == 200
    comparison = response.json()['context']['cantons'][0]['comparison']
    assert comparison['zona']['id'] == 'canas'
    assert len(comparison['rotations']) == 3
    assert simulator.requests[0][1].zona.id == 'canas'
    prompt = assistant.payloads[0]['context']['cantons'][0]['comparison']
    assert 'daily_balance' not in prompt['rotations'][0]['runs'][0]
    assert prompt['rotations'][0]['runs'][0]['period_start']
    canonical_request = simulator.requests[0][1].model_dump(mode='json')
    direct = client.post('/cantons/canas/compare', json=canonical_request)
    assert direct.status_code == 200
    assert [item['metrics'] for item in direct.json()['rotations']] == [item['metrics'] for item in comparison['rotations']]


def test_simulator_failure_is_explicit_in_chat_and_http():
    class Simulator:
        def point(self, canton_id): return CantonSimulator().point(canton_id)
        def compare(self, *args): raise CantonSimulationError(503, 'Clima incompleto.')
        def recent(self, *args, **kwargs): raise CantonSimulationError(503, 'Clima incompleto.')
    assistant = Assistant()
    client = TestClient(create_app(chat_context=CantonContext(cache=ClimateCache()),
                                   canton_simulator=Simulator(), gemini=assistant))
    response = client.post('/chat', json={'question': '¿Qué hago?',
                           'selection': selection(scenario_id='neutral', years=[2025])})
    assert response.status_code == 200
    canton = response.json()['context']['cantons'][0]
    assert canton['comparison_unavailable'] == 'Clima incompleto.'
    assert canton['replays_unavailable'] == 'Clima incompleto.'
    assert client.get('/cantons/canas/recent').status_code == 503


def test_replay_prompt_matches_common_cutoff_in_simulation_table():
    def day(iso, value):
        return {'date': iso, 'crop_water_demand_mm': value,
                'modeled_water_deficit_mm': value, 'water_stress': True}
    seasons = [{'year': year, 'start': f'{year}-01-01', 'end': end,
                'runs': [{'rotation_id': 'rice_melon', 'daily_balance': rows}]}
               for year, end, rows in [
                   (2026, '2026-01-02', [day('2026-01-01', 2), day('2026-01-02', 2)]),
                   (2025, '2025-12-31', [day('2025-01-01', 1), day('2025-01-02', 1), day('2025-01-03', 99)]),
               ]]
    result = prompt_context({'cantons': [{'id': 'canas', 'replays': {'seasons': seasons}}]})
    replays = result['cantons'][0]['replays']
    assert replays['comparison_cutoff_mmdd'] == '01-02'
    assert replays['seasons'][1]['runs'][0]['metrics']['modeled_water_deficit_mm']['total'] == 2
    assert replays['seasons'][1]['runs'][0]['summary_end'] == '2025-01-02'
