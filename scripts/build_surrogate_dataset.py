"""Export rows to fit a surrogate of the FAO-56 kernel."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from backend.app.api.schemas.contracts import Metrics, SimulationInput
from backend.app.application.compare import environment_fingerprint
from backend.app.infrastructure.cache import write_json
from backend.app.simulation.kernel import simulate_rotation
from scripts.smoke_kernel import smoke_inputs


def build_dataset(inputs, *, validation_start, test_start):
    if validation_start >= test_start or not inputs or len({i.mock for i in inputs}) != 1:
        raise ValueError('expected homogeneous inputs and validation_start < test_start')
    rows, rejected = [], []
    for supplied in inputs:
        case = SimulationInput.model_validate(supplied.model_dump())
        year = case.climate.year
        # Purge seasons spanning a split boundary so no weather date from
        # the later split also contributes to an earlier split's labels.
        if any(year < boundary <= case.climate.end.year for boundary in (validation_start, test_start)):
            rejected.append({'year': year, 'rotation_id': case.rotation.rotation_id,
                             'reason': 'season_crosses_split_boundary'})
            continue
        if not case.mock and any(
            day.precipitation_mm is None or day.et0_mm is None for day in case.climate.days
        ):
            rejected.append({'year': year, 'rotation_id': case.rotation.rotation_id,
                             'reason': 'incomplete_rain_or_et0'})
            continue
        result = simulate_rotation(climate=case.climate, soil=case.soil,
                                   rotation=case.rotation, assumptions=case.assumptions)
        labels = Metrics.model_validate(result['metrics']).model_dump()
        if any(label is None for label in labels.values()):
            rejected.append({'year': year, 'rotation_id': case.rotation.rotation_id,
                             'reason': 'missing_kernel_label'})
            continue
        days = case.climate.days
        predictors = {'rotation_id': case.rotation.rotation_id,
                      'latitude': case.zona.latitude, 'longitude': case.zona.longitude,
                      'rain_mm': sum(d.precipitation_mm for d in days) if all(d.precipitation_mm is not None for d in days) else None,
                      'et0_mm': sum(d.et0_mm for d in days) if all(d.et0_mm is not None for d in days) else None,
                      'irrigation_mode': case.assumptions.irrigation_mode,
                      'irrigation_mm': sum(case.assumptions.irrigation_mm_by_date.values()),
                      'initial_soil_water_fraction': case.assumptions.initial_soil_water_fraction,
                      'soil_field_capacity_m3_m3': case.soil.field_capacity_m3_m3,
                      'soil_wilting_point_m3_m3': case.soil.wilting_point_m3_m3,
                      'rooting_depth_m': case.soil.rooting_depth_m}
        for index, cycle in enumerate(case.rotation.cycles, 1):
            predictors.update({f'crop_{index}': cycle.crop_id, f'parameter_set_{index}': cycle.parameter_set_id,
                f'sowing_month_{index}': cycle.sowing_date.month, f'sowing_day_{index}': cycle.sowing_date.day,
                f'cycle_days_{index}': (cycle.harvest_date-cycle.sowing_date).days+1})
        rows.append({'features': predictors, 'labels': labels, 'label_source': 'simulation',
                     'climate_year': year, 'replay_end': case.climate.end.isoformat(), 'location_id': case.zona.id,
                     'split': 'test' if year >= test_start else 'validation' if year >= validation_start else 'train',
                     'environment_id': environment_fingerprint(case), 'model_version': result['model_version'],
                     'source_refs': sorted(set(case.source_refs + result['source_refs'])),
                     'warnings': list(dict.fromkeys(case.warnings + result['warnings']))})
    return {'_mock': inputs[0].mock, 'task': 'simulator_surrogate', 'feature_timing': 'full_historical_scenario_replay',
            'rows': rows, 'rejected': rejected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--inputs', type=Path)
    source.add_argument('--demo', action='store_true', help='Use synthetic smoke inputs')
    parser.add_argument('--validation-start', type=int, default=2014)
    parser.add_argument('--test-start', type=int, default=2018)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.demo:
        inputs = smoke_inputs(range(2010, 2021))
        provenance = {'source': 'scripts.smoke_kernel.smoke_inputs', 'years': [2010, 2020]}
    else:
        body = args.inputs.read_bytes()
        inputs = [SimulationInput.model_validate(row) for row in json.loads(body)]
        provenance = {'source': args.inputs.name, 'sha256': sha256(body).hexdigest()}
    if args.inputs and args.inputs.resolve() == args.output.resolve():
        parser.error('output must not overwrite input')
    dataset = build_dataset(inputs, validation_start=args.validation_start, test_start=args.test_start)
    write_json(args.output, dataset | {'provenance': provenance})
    print(f'{len(dataset["rows"])} rows with simulated labels, {len(dataset["rejected"])} excluded')


if __name__ == '__main__':
    main()
