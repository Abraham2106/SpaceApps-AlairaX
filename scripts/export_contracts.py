"""Generate deterministic M1 examples and frontend mocks, without a scientific kernel.

Run from the repository root: python -m scripts.export_contracts
Every numeric value here is synthetic UI/test data, including analog distances.
"""

import argparse
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

from backend.app.api.schemas.contracts import (
    AnalogYear, ClimateDay, ClimateSeason, CompareRequest, CompareResponse,
    CropCycle, Metrics, ModelAssumptions, RotationSchedule, SimulationInput,
    SimulationResult, SoilProfile, Zone,
)
from backend.app.intelligence.counterfactual import compare_runs
from backend.app.application.prepare_inputs import ComparisonSetup

ROOT = Path(__file__).resolve().parents[1]
GENERATED = datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)
ROTATIONS = ('rice_melon', 'rice_legume', 'rice_sorghum')
SCENARIOS = ('strong_el_nino', 'neutral', 'la_nina', 'like_2026')
SCENARIO_K = {'strong_el_nino': 3, 'neutral': 5, 'la_nina': 5, 'like_2026': 5}
MOCK_WARNING = 'SYNTHETIC MOCK: UI and contract testing only; not observed climate or FAO-56 results.'
MOCK_ASSUMPTIONS = [
    'All climate, metrics and analog distances are synthetic fixtures.',
    'Crop dates are provisional placeholders pending Ant and Justin.',
    'No agronomic parameters, soil measurements or KNN search were used.',
]
ZONE = Zone(id='guanacaste_candidate', name='Guanacaste — provisional test point',
            latitude=10.55, longitude=-85.50, validated=False)


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(value, 'model_dump'):
        value = value.model_dump(mode='json', by_alias=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def make_fixture() -> SimulationInput:
    """A complete April–December season; missing real parameters remain null."""
    start, end = date(2015, 4, 1), date(2015, 12, 31)
    days = []
    for offset in range((end - start).days + 1):
        days.append(ClimateDay(
            date=start + timedelta(days=offset), precipitation_mm=5.0 if offset % 3 == 0 else 0.0,
            tmin_c=22.0, tmax_c=32.0, relative_humidity_pct=70.0,
            wind_speed_2m_m_s=2.0, solar_radiation_mj_m2_day=18.0, et0_mm=None,
        ))
    return SimulationInput(
        mock=True, generado=GENERATED, zona=ZONE, source_refs=['synthetic-fixture-v1'],
        warnings=[MOCK_WARNING, 'Soil profile and crop parameters are unknown; real execution is blocked.'],
        scenario_id='neutral', climate=ClimateSeason(year=2015, start=start, end=end, days=days),
        soil=SoilProfile(field_capacity_m3_m3=None, wilting_point_m3_m3=None,
                         rooting_depth_m=None, source_refs=[]),
        rotation=RotationSchedule(rotation_id='rice_melon', calendar_status='provisional', cycles=[
            CropCycle(crop_id='rice', sowing_date=date(2015, 5, 1), harvest_date=date(2015, 8, 31), parameter_set_id=None),
            CropCycle(crop_id='melon', sowing_date=date(2015, 10, 1), harvest_date=date(2015, 12, 31), parameter_set_id=None),
        ]),
        assumptions=ModelAssumptions(irrigation_mode='unspecified', irrigation_mm_by_date={},
                                     initial_soil_water_fraction=None, notes=MOCK_ASSUMPTIONS),
    )


def make_mock_runs(scenario_id='neutral'):
    """Construct a small fixed mock sample. These years are not KNN selections."""
    analogs = [AnalogYear(year=year, distance=distance) for year, distance in
               [(1982, .1), (1997, .2), (2002, .3), (2015, .4), (2023, .5)]]
    if scenario_id == 'strong_el_nino':
        analogs = [AnalogYear(year=year, distance=distance) for year, distance in
                   [(1997, .1), (2015, .2), (2023, .3)]]
    runs = []
    for i, analog in enumerate(analogs):
        for r, rotation in enumerate(ROTATIONS):
            # Vary the tradeoff so the fixture does not imply a recommended crop.
            runs.append(SimulationResult(
                mock=True, generado=GENERATED, zona=ZONE, source_refs=['synthetic-fixture-v1'],
                warnings=[MOCK_WARNING], rotation_id=rotation, scenario_id=scenario_id, year=analog.year,
                metrics=Metrics(crop_water_demand_mm=700 + 40 * i + 20 * r,
                                modeled_water_deficit_mm=100 + 20 * i - 10 * r,
                                water_stress_days=10 + i + r),
                daily_balance=[], assumptions=MOCK_ASSUMPTIONS, model_version='synthetic-mock-v1',
                environment_id=sha256(f'synthetic-fixture-v1:{scenario_id}:{analog.year}'.encode()).hexdigest(),
            ))
    return analogs, runs


def make_setup_fixture() -> ComparisonSetup:
    fixture = make_fixture()
    rotations = []
    for rotation_id, crop_id in [('rice_melon', 'melon'), ('rice_legume', 'legume'), ('rice_sorghum', 'sorghum')]:
        rotation = fixture.rotation.model_copy(deep=True)
        rotation.rotation_id = rotation_id
        rotation.cycles[1].crop_id = crop_id
        rotations.append(rotation)
    return ComparisonSetup(
        mock=True, generado=GENERATED, zona=ZONE, source_refs=['synthetic-fixture-v1'],
        warnings=[MOCK_WARNING], reviewed_by='synthetic-fixture-only-not-scientific-approval',
        soil=fixture.soil, rotations_by_year={2015: rotations},
        assumptions_by_year={2015: fixture.assumptions})


def make_mock_response(scenario_id='neutral') -> CompareResponse:
    analogs, runs = make_mock_runs(scenario_id)
    request = CompareRequest(zona=ZONE, scenario_id=scenario_id, k=SCENARIO_K[scenario_id])
    response = compare_runs(request, analogs, runs)
    # compare_runs records execution time; the checked-in fixture must remain deterministic.
    response.generado = GENERATED
    return response


def export(root: Path = ROOT, *, public_fixtures=True):
    contracts_dir = root / 'docs' / 'contracts'
    examples = root / 'datasets' / 'examples'
    public_data = root / 'frontend' / 'public' / 'data'
    for model in (SimulationInput, SimulationResult, CompareRequest, CompareResponse, ComparisonSetup):
        write_json(contracts_dir / f'{model.__name__}.schema.json', model.model_json_schema(by_alias=True))
    write_json(examples / 'simulation-input.mock.json', make_fixture())
    _, runs = make_mock_runs()
    write_json(examples / 'simulation-result.mock.json', runs[0])
    write_json(examples / 'compare-request.mock.json', CompareRequest(zona=ZONE, scenario_id='neutral'))
    write_json(examples / 'comparison-setup.mock.json', make_setup_fixture())
    if not public_fixtures:
        return
    common = dict(schema_version='0.1.0', _mock=True, generado=GENERATED.isoformat(),
                  zona=ZONE.model_dump(mode='json'), source_refs=['synthetic-fixture-v1'], warnings=[MOCK_WARNING])
    write_json(public_data / 'rotations.json', dict(common, rotations=[
        dict(rotation_id=rotation, name=name, baseline=rotation == 'rice_melon',
             crops=['rice', crop], calendar_status='provisional',
             calendar=None, parameter_set_id=None, evidence_status='pending')
        for rotation, name, crop in [('rice_melon', 'Arroz → melón', 'melon'),
                                      ('rice_legume', 'Arroz → leguminosa', 'legume'),
                                      ('rice_sorghum', 'Arroz → sorgo', 'sorghum')]
    ]))
    write_json(public_data / 'scenarios.json', dict(common, scenarios=[
        dict(scenario_id=scenario, name=name, result_file=f'compare-{scenario}.json',
             selection_status='synthetic_fixture_not_knn', k=SCENARIO_K[scenario],
             sample_warning='Only 3 analog years; descriptive quantiles have limited support.'
             if scenario == 'strong_el_nino' else None)
        for scenario, name in zip(SCENARIOS, ['Niño fuerte', 'Neutro', 'Niña', 'Como 2026'])
    ]))
    for scenario in SCENARIOS:
        write_json(public_data / f'compare-{scenario}.json', make_mock_response(scenario))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend-fixtures', action='store_true',
                        help='Replace the static frontend comparisons with synthetic QA fixtures')
    args = parser.parse_args()
    export(public_fixtures=args.frontend_fixtures)
    print('Exported schemas and synthetic examples.'
          + (' Replaced static comparisons with QA fixtures.' if args.frontend_fixtures else ''))
