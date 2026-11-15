"""Canton expansion must change the physical inputs, not relabel Liberia runs."""

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

import pytest

from backend.app.api.schemas.contracts import CompareRequest, CompareResponse
from backend.app.application.canton_simulation import CantonSimulator, CantonSimulationError

ROOT = Path(__file__).resolve().parents[2]


class PointCache:
    def __init__(self, *, missing=None, fail=False):
        self.missing, self.fail = missing, fail
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        if self.fail:
            raise URLError('unavailable')
        query = parse_qs(urlparse(url).query)
        start = datetime.strptime(query['start'][0], '%Y%m%d').date()
        end = datetime.strptime(query['end'][0], '%Y%m%d').date()
        lat, lon = float(query['latitude'][0]), float(query['longitude'][0])
        # Different own-point climates with the same scenario must produce
        # different water balances, even before soil differences are considered.
        rain = 4.0 if lat < 10.5 else 0.2
        definitions = {
            'PRECTOTCORR': ('mm/day', rain), 'T2M_MIN': ('C', 21.0),
            'T2M_MAX': ('C', 33.0), 'RH2M': ('%', 65.0),
            'WS2M': ('m/s', 2.0), 'ALLSKY_SFC_SW_DWN': ('MJ/m^2/day', 19.0),
        }
        days = [start + timedelta(days=i) for i in range((end-start).days+1)]
        params = {name: {day.strftime('%Y%m%d'): value for day in days}
                  for name, (_, value) in definitions.items()}
        if self.missing and start <= self.missing <= end:
            params['PRECTOTCORR'][self.missing.strftime('%Y%m%d')] = -999
        payload = {'properties': {'parameter': params},
                   'parameters': {name: {'units': unit} for name, (unit, _) in definitions.items()},
                   'header': {'fill_value': -999}, 'geometry': {'coordinates': [lon, lat, 100]}}
        return json.dumps(payload).encode(), {
            'url': url, 'fetched_at': datetime.now(timezone.utc).isoformat(), 'status': 200,
        }


@pytest.fixture
def catalog():
    return json.loads((ROOT/'datasets/processed/analogs/analogos.json').read_bytes())


def request_for(service, canton, **updates):
    _, zone, _ = service.point(canton)
    return CompareRequest(zona=zone, scenario_id='neutral', k=1, **updates)


def test_catalog_is_exactly_guanacaste_and_soil_identities_match():
    service = CantonSimulator(cache=PointCache())
    geo = json.loads((ROOT/'frontend/public/geo/cantons.geojson').read_bytes())
    ids = {feature['id'] for feature in geo['features'] if feature['properties']['guanacaste']}
    assert set(json.loads(service.catalog_path.read_bytes())) == ids
    assert len(ids) == 11
    profiles = []
    for canton in ids:
        point, zone, soil = service.point(canton)
        assert zone.id == canton and zone.validated is False
        assert zone.latitude == point['latitude']
        assert soil.field_capacity_m3_m3 > soil.wilting_point_m3_m3
        assert f'lat={zone.latitude}' in soil.source_refs[0]
        profiles.append(soil.field_capacity_m3_m3)
    assert len(set(profiles)) == 11


def test_distinct_canton_climate_soil_and_paired_environment(catalog):
    cache = PointCache()
    service = CantonSimulator(cache=cache)
    outputs = []
    for canton in ('canas', 'liberia'):
        request = request_for(service, canton)
        result = service.compare(canton, request, catalog, ROOT/'outputs/inputs')
        CompareResponse.model_validate(result.model_dump())
        assert result.zona.id == canton and not result.mock
        assert result.zona.latitude != 10.55
        fingerprints = {rotation.runs[0].environment_id for rotation in result.rotations}
        assert len(fingerprints) == 1
        assert all(len(rotation.runs[0].daily_balance) == 365 for rotation in result.rotations)
        assert any('selección regional' in warning for warning in result.warnings)
        assert any('no una finca validada' in warning for warning in result.warnings)
        assert not any('latitude=10.55&longitude=-85.5' in ref for ref in result.source_refs)
        outputs.append(result)
    assert outputs[0].rotations[0].metrics.modeled_water_deficit_mm.p50 != outputs[1].rotations[0].metrics.modeled_water_deficit_mm.p50
    assert outputs[0].rotations[0].runs[0].environment_id != outputs[1].rotations[0].runs[0].environment_id
    assert len(cache.calls) == 2


def test_unknown_canton_mismatched_zone_and_unavailable_scenario(catalog):
    service = CantonSimulator(cache=PointCache())
    with pytest.raises(CantonSimulationError, match='Guanacaste') as error:
        service.point('san-jose')
    assert error.value.status == 404
    request = request_for(service, 'canas')
    with pytest.raises(CantonSimulationError, match='coincidir') as error:
        service.compare('liberia', request, catalog, ROOT/'outputs/inputs')
    assert error.value.status == 422
    unavailable = {**catalog, 'scenarios': {}}
    with pytest.raises(CantonSimulationError) as error:
        service.compare('canas', request, unavailable, ROOT/'outputs/inputs')
    assert error.value.status == 409


def test_missing_climate_rejects_without_imputing_or_falling_back(catalog):
    service = CantonSimulator(cache=PointCache(missing=date(1984, 8, 1)))
    with pytest.raises(CantonSimulationError, match='no se sustituyen') as error:
        service.compare('canas', request_for(service, 'canas'), catalog, ROOT/'outputs/inputs')
    assert error.value.status == 503
    failed = CantonSimulator(cache=PointCache(fail=True))
    with pytest.raises(CantonSimulationError, match='Clima'):
        failed.compare('canas', request_for(failed, 'canas'), catalog, ROOT/'outputs/inputs')


def test_recent_replay_is_local_with_transparent_provider_latency():
    service = CantonSimulator(cache=PointCache(missing=date(2017, 1, 9)),
                              today=lambda: date(2017, 1, 10))
    result = service.recent('canas')
    assert result['zona']['id'] == 'canas'
    assert result['model_scope'] == 'regional_pilot'
    season = result['seasons'][0]
    assert season['year'] == 2017
    assert season['start'] == '2017-01-01' and season['end'] == '2017-01-08'
    assert season['complete'] is False
    assert season['evidence']['requested_end'] == '2017-01-09'
    assert len(season['runs']) == 3
    assert all(len(run['daily_balance']) == 8 for run in season['runs'])
    assert all(run['daily_balance'][0]['date'] == '2017-01-01' for run in season['runs'])
    point_refs = [source for source in result['source_refs']
                  if 'power.larc.nasa.gov/api/' in source or 'rest.isric.org/' in source]
    assert all('latitude=10.44154' in source or 'lat=10.44154' in source for source in point_refs)
    assert len(point_refs) == 2


def test_recent_warmup_gap_keeps_unknown_state_without_imputation():
    service = CantonSimulator(cache=PointCache(missing=date(2016, 8, 1)),
                              today=lambda: date(2017, 1, 10))
    result = service.recent('canas')
    season = result['seasons'][0]
    assert season['complete'] is False
    assert season['evidence']['missing_forcing_dates'] == ['2016-08-01']
    assert season['evidence']['simulation_valid_through'] == '2016-07-31'
    assert all(day['soil_water_storage_mm'] is None for run in season['runs'] for day in run['daily_balance'])
    assert all(day['modeled_water_deficit_mm'] is None for run in season['runs'] for day in run['daily_balance'])
    assert 'no se imputan' in season['runs'][0]['warnings'][0]


def test_recent_internal_gap_preserves_only_known_prefix():
    service = CantonSimulator(cache=PointCache(missing=date(2017, 1, 5)),
                              today=lambda: date(2017, 1, 10))
    season = service.recent('canas')['seasons'][0]
    rows = season['runs'][0]['daily_balance']
    assert len(rows) == 9
    assert all(row['soil_water_storage_mm'] is not None for row in rows[:4])
    assert all(row['soil_water_storage_mm'] is None for row in rows[4:])
    assert season['evidence']['simulation_valid_through'] == '2017-01-04'


def test_comparison_cache_coalesces_and_returns_defensive_copies(catalog):
    cache = PointCache()
    service = CantonSimulator(cache=cache)
    request = request_for(service, 'canas')
    first = service.compare('canas', request, catalog, ROOT/'outputs/inputs')
    first.rotations[0].runs.clear()
    second = service.compare('canas', request, catalog, ROOT/'outputs/inputs')
    assert len(second.rotations[0].runs) == 1
    assert len(cache.calls) == 1


@pytest.mark.parametrize('years', [[], [2016], [2027], [2017, 2017], ['2017']])
def test_recent_invalid_years_reject_without_fetch(years):
    cache = PointCache()
    service = CantonSimulator(cache=cache)
    with pytest.raises(CantonSimulationError) as error:
        service.recent('canas', years=years)
    assert error.value.status == 422
    assert not cache.calls


def test_recent_selected_year_and_export_verification(tmp_path):
    from scripts.export_canton_simulations import verified_recent

    service = CantonSimulator(cache=PointCache(), today=lambda: date(2019, 1, 10))
    result = service.recent('canas', years=[2017])
    assert [season['year'] for season in result['seasons']] == [2017]
    _, zone, _ = service.point('canas')
    path = tmp_path/'recent.json'
    path.write_text(json.dumps(result), encoding='utf-8')
    # Full release validation requires all available years; an intentionally
    # narrowed chat replay cannot accidentally qualify as the complete export.
    assert not verified_recent(path, zone, last_day=date(2019, 1, 9))
    assert verified_recent(path, zone, last_day=date(2017, 12, 31))


def test_export_verification_rejects_stale_recent_request_end(tmp_path):
    from scripts.export_canton_simulations import verified_recent

    service = CantonSimulator(cache=PointCache(), today=lambda: date(2017, 1, 10))
    result = service.recent('canas')
    _, zone, _ = service.point('canas')
    path = tmp_path/'recent.json'
    path.write_text(json.dumps(result), encoding='utf-8')
    assert verified_recent(path, zone, last_day=date(2017, 1, 9))
    assert not verified_recent(path, zone, last_day=date(2017, 1, 10))
