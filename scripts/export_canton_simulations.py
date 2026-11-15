"""Export real regional-pilot comparisons/recent replays for Guanacaste's eleven points.

Run from the repository root. NASA failures stop the export; no other canton's
data or synthetic values are substituted. Completed files can be verified and
reused on a subsequent --skip-existing run.
"""

import argparse
from datetime import date, timedelta
import json
from pathlib import Path

from backend.app.api.schemas.contracts import CompareRequest, CompareResponse, DailyBalance
from backend.app.application.canton_simulation import CantonSimulator, CantonSimulationError, ROOT
from backend.app.infrastructure.cache import write_json
from backend.app.simulation.version import MODEL_VERSION

SCENARIOS = ('strong_el_nino', 'neutral', 'la_nina', 'like_2026')
ROTATIONS = {'rice_melon', 'rice_legume', 'rice_sorghum'}


def verified_comparison(path: Path, request: CompareRequest, analogs: dict) -> bool:
    try:
        result = CompareResponse.model_validate_json(path.read_bytes())
        if (result.mock or result.zona != request.zona or result.scenario_id != request.scenario_id
                or result.baseline_rotation_id != request.baseline_rotation_id
                or {rotation.rotation_id for rotation in result.rotations} != ROTATIONS
                or len(result.analog_years) != request.k):
            return False
        expected_years = [item['year'] for item in analogs['scenarios'][request.scenario_id]['neighbors'][:request.k]]
        if [item.year for item in result.analog_years] != expected_years:
            return False
        return all(run.model_version == MODEL_VERSION and run.daily_balance
                   for rotation in result.rotations for run in rotation.runs)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def verified_recent(path: Path, zone, *, last_day: date) -> bool:
    try:
        result = json.loads(path.read_bytes())
        expected_years = list(range(2017, min(2026, last_day.year) + 1))
        if (result.get('_mock') is not False or result.get('model_scope') != 'regional_pilot'
                or result.get('zona') != zone.model_dump(mode='json')
                or result.get('model_version') != MODEL_VERSION
                or [season['year'] for season in result['seasons']] != expected_years):
            return False
        for season in result['seasons']:
            start, end = date.fromisoformat(season['start']), date.fromisoformat(season['end'])
            requested_end = min(date(season['year'], 12, 31), last_day)
            if (start != date(season['year'], 1, 1) or end < start or end > requested_end
                    or season['evidence']['requested_end'] != requested_end.isoformat()):
                return False
            if season['year'] < last_day.year and end != requested_end:
                return False
            has_gaps = bool(season['evidence'].get('missing_forcing_dates'))
            if season['complete'] != (end == date(season['year'], 12, 31) and not has_gaps):
                return False
            if {run['rotation_id'] for run in season['runs']} != ROTATIONS or len(season['runs']) != 3:
                return False
            expected_dates = [start + timedelta(days=i) for i in range((end-start).days+1)]
            for run in season['runs']:
                if run.get('model_version') != MODEL_VERSION:
                    return False
                if [DailyBalance.model_validate(day).date for day in run['daily_balance']] != expected_dates:
                    return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--canton', action='append', help='One Guanacaste canton id; repeat to select several.')
    parser.add_argument('--skip-existing', action='store_true', help='Reuse only files passing contract/zone/year verification.')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'frontend/public/data/cantons')
    parser.add_argument('--analogs', type=Path, default=ROOT/'datasets/processed/analogs/analogos.json')
    parser.add_argument('--inputs-dir', type=Path, default=ROOT/'outputs/inputs')
    args = parser.parse_args()
    service = CantonSimulator()
    analogs = json.loads(args.analogs.read_bytes())
    catalog = json.loads(service.catalog_path.read_bytes())
    cantons = list(dict.fromkeys(args.canton or catalog.keys()))
    if set(cantons) - catalog.keys():
        parser.error('Only ids in the Guanacaste pilot catalog are accepted.')
    for index, canton in enumerate(cantons, 1):
        _, zone, _ = service.point(canton)
        print(f'[{index}/{len(cantons)}] {canton}', flush=True)
        destination = args.output_dir / canton
        for scenario in SCENARIOS:
            scenario_data = analogs['scenarios'][scenario]
            if scenario_data['status'] != 'available':
                raise CantonSimulationError(409, f'{scenario}: regional analog selection is unavailable')
            request = CompareRequest(zona=zone, scenario_id=scenario, k=scenario_data['k'])
            path = destination / f'compare-{scenario}.json'
            if args.skip_existing and verified_comparison(path, request, analogs):
                print(f'  {scenario}: verified existing', flush=True)
                continue
            result = service.compare(canton, request, analogs, args.inputs_dir)
            write_json(path, result.model_dump(mode='json', by_alias=True))
            print(f'  {scenario}: exported {len(result.analog_years)} analogs, 3 rotations', flush=True)
        path = destination / 'recent-seasons.json'
        if args.skip_existing and verified_recent(path, zone, last_day=service.today()-timedelta(days=1)):
            print('  recent: verified existing', flush=True)
        else:
            recent = service.recent(canton)
            write_json(path, recent)
            print(f'  recent: exported {len(recent["seasons"])} years', flush=True)
    print(f'Completed {len(cantons)} Guanacaste cantons.', flush=True)


if __name__ == '__main__':
    main()
