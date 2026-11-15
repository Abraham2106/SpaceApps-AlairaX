"""Exercise the real kernel with explicitly synthetic inputs and analogs."""

import argparse
from datetime import date, timedelta
from pathlib import Path

from backend.app.api.schemas.contracts import ClimateDay, ClimateSeason, ModelAssumptions, SoilProfile
from backend.app.infrastructure.cache import write_json
from backend.app.simulation.kernel import simulate_rotation, template_rotation
from scripts.export_contracts import ZONE, make_fixture
from scripts.run_comparison import compare_from_analogs


def smoke_inputs(years):
    inputs = []
    for year in years:
        start, end = date(year, 5, 1), date(year + 1, 4, 30)
        days = [ClimateDay(date=start + timedelta(days=i), precipitation_mm=2.0,
                          tmin_c=22, tmax_c=32, relative_humidity_pct=70,
                          wind_speed_2m_m_s=2, solar_radiation_mj_m2_day=18, et0_mm=4)
                for i in range((end-start).days + 1)]
        for rotation, second in [('rice_melon', 'melon'), ('rice_legume', 'legume'), ('rice_sorghum', 'sorghum')]:
            simulation = make_fixture()
            simulation.climate = ClimateSeason(year=year, start=start, end=end, days=days)
            # Test-only override prevents overlaps without changing the scientific YAML.
            simulation.rotation = template_rotation(rotation, year,
                sowing_dates={second: date(year, 11, 15)})
            simulation.soil = SoilProfile(field_capacity_m3_m3=.30, wilting_point_m3_m3=.15,
                                          rooting_depth_m=1, source_refs=['synthetic-soil-fixture'])
            simulation.assumptions = ModelAssumptions(irrigation_mode='rainfed', irrigation_mm_by_date={},
                initial_soil_water_fraction=.5, notes=['Synthetic integration fixture; all rotations rainfed.'])
            simulation.warnings = ['SYNTHETIC INPUTS AND ANALOGS: real kernel integration test only.',
                                   'Second crop sowing overridden for this test; no scientific calendar approval.']
            inputs.append(simulation)
    return inputs


def run_smoke():
    years = (2014, 2015)
    inputs = smoke_inputs(years)
    document = {'_mock': True, 'zona': ZONE.model_dump(mode='json'),
        'source_refs': ['synthetic-analog-fixture'], 'warnings': ['KNN was not run; years selected for testing.'],
        'scenarios': {'neutral': {'status': 'available', '_mock': True, 'k': len(years),
                                  'neighbors': [{'year': year, 'distance': 0} for year in years]}}}
    return compare_from_analogs(document, 'neutral', inputs, simulate_rotation=simulate_rotation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('datasets/examples/kernel-smoke.mock.json'))
    args = parser.parse_args()
    result = run_smoke()
    write_json(args.output, result.model_dump(mode='json', by_alias=True))
    print(f'{args.output}: 3 rotations x 2 synthetic analog years; real kernel; _mock=true')


if __name__ == '__main__':
    main()
