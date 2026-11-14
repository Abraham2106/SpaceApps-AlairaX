"""Report calendar conflicts without modifying agronomic assumptions."""

import argparse
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

from backend.app.infrastructure.cache import write_json
from backend.app.simulation.kernel import CROPS_YAML, ROTATIONS_YAML
from backend.app.simulation.parameters import load_crops, load_rotations
from backend.app.simulation.water_balance import resolve_season_date


def inspect_calendars(year=2015):
    crops, rotations = load_crops(CROPS_YAML), load_rotations(ROTATIONS_YAML)
    start, end = date(year, 5, 1), date(year + 1, 4, 30)
    reports = []
    for rotation in rotations.rotations:
        cycles, conflicts, pending = [], [], []
        for segment in rotation.segments:
            params = crops.crops[segment.crop_id]
            if not params.verified:
                pending.append(segment.crop_id)
            if params.stage_days is None:
                conflicts.append({'type': 'missing_stage_duration', 'crop_id': segment.crop_id})
                continue
            sowing = resolve_season_date(segment.sowing_mmdd, year)
            harvest = sowing + timedelta(days=sum(params.stage_days)-1)
            cycle = {'crop_id': segment.crop_id, 'sowing': sowing.isoformat(),
                     'harvest': harvest.isoformat(), 'duration_days': sum(params.stage_days)}
            for previous in cycles:
                if sowing <= date.fromisoformat(previous['harvest']) and harvest >= date.fromisoformat(previous['sowing']):
                    conflicts.append({'type': 'overlap', 'crops': [previous['crop_id'], segment.crop_id],
                                      'previous_harvest': previous['harvest'], 'next_sowing': sowing.isoformat()})
            if sowing < start or harvest > end:
                conflicts.append({'type': 'outside_season', 'crop_id': segment.crop_id})
            cycles.append(cycle)
        reports.append({'rotation_id': rotation.rotation_id, 'calendar_status': 'provisional',
                        'cycles': cycles, 'conflicts': conflicts, 'unverified_crops': pending})
    return {'_mock': False, 'simulation_run': False, 'season_year': year,
            'start': start.isoformat(), 'end': end.isoformat(), 'status': 'blocked_pending_review',
            'source_artifacts': [{'file': p.as_posix(), 'sha256': sha256(p.read_bytes()).hexdigest()}
                                 for p in (CROPS_YAML, ROTATIONS_YAML)], 'rotations': reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--year', type=int, default=2015)
    parser.add_argument('--output', type=Path, default=Path('datasets/processed/readiness/calendars.json'))
    args = parser.parse_args()
    report = inspect_calendars(args.year)
    write_json(args.output, report)
    for rotation in report['rotations']:
        print(f'{rotation["rotation_id"]}: {len(rotation["conflicts"])} calendar conflicts; parameters provisional')


if __name__ == '__main__':
    main()
