"""Export 2022–2026 daily pilot replays for the recent-season selectors."""

from datetime import date
import json
from pathlib import Path

from backend.app.api.schemas.contracts import ClimateSeason, DailyBalance
from backend.app.application.prepare_inputs import ComparisonSetup
from backend.app.infrastructure.cache import write_json
from backend.app.simulation.et0 import et0_for_days
from backend.app.simulation.kernel import simulate_rotation

ROOT = Path(__file__).resolve().parents[1]


def main():
    setup = ComparisonSetup.model_validate_json(
        (ROOT / 'configs/regions/guanacaste-pilot.setup.json').read_bytes())
    sources = []
    documents = {}
    for path in sorted((ROOT / 'datasets/processed/climate').glob('power_10.55_-85.5_*.json')):
        document = json.loads(path.read_bytes())
        year = date.fromisoformat(document['start']).year
        if year not in documents or len(document['days']) > len(documents[year]['days']):
            documents[year] = document
    for path in sorted((ROOT / 'datasets/processed/recent-climate').glob('power-*.json')):
        document = json.loads(path.read_bytes())
        documents[date.fromisoformat(document['start']).year] = document
    rows = {row['date']: row for year, doc in documents.items() if year >= 2021 for row in doc['days']}
    sources = sorted({ref for year, doc in documents.items() if year >= 2021 for ref in doc['source_refs']})
    last_available = max(day for day, row in rows.items()
                         if row['precipitation_mm'] is not None and row['tmax_c'] is not None)
    base_year = min(setup.rotations_by_year)
    seasons = []
    for year in range(2022, 2027):
        start = date(year, 1, 1)
        warmup = date(year - 1, 5, 1)
        end = min(date(year, 12, 31), date.fromisoformat(last_available))
        days = [dict(rows[day]) for day in sorted(rows) if warmup.isoformat() <= day <= end.isoformat()]
        elevation = documents[year]['provider_geometry']['coordinates'][2]
        for row, et0 in zip(days, et0_for_days(days, setup.zona.latitude, elevation)):
            row['et0_mm'] = et0
        climate = ClimateSeason(year=warmup.year, start=warmup, end=end, days=days)
        runs = []
        for template in setup.rotations_by_year[base_year]:
            rotation = template.model_copy(deep=True)
            cycles = []
            for crop_year in (year - 1, year):
                for original in template.cycles:
                    cycle = original.model_copy(deep=True)
                    cycle.sowing_date = cycle.sowing_date.replace(year=cycle.sowing_date.year + crop_year - base_year)
                    cycle.harvest_date = cycle.harvest_date.replace(year=cycle.harvest_date.year + crop_year - base_year)
                    cycles.append(cycle)
            rotation.cycles = cycles
            result = simulate_rotation(climate=climate, soil=setup.soil, rotation=rotation,
                                       assumptions=setup.assumptions_by_year[base_year])
            runs.append({
                'rotation_id': rotation.rotation_id,
                'daily_balance': [DailyBalance.model_validate(day).model_dump(mode='json')
                                  for day in result['daily_balance'] if day['date'].year == year],
                'warnings': result['warnings'],
            })
        seasons.append({'year': year, 'start': start.isoformat(), 'end': end.isoformat(),
                        'complete': end == date(year, 12, 31), 'runs': runs})
        print(year, start, end, len(runs[0]['daily_balance']), 'published days', flush=True)
    write_json(ROOT / 'frontend/public/data/recent-seasons.json', {
        '_mock': False, 'zona': setup.zona.model_dump(mode='json'),
        'model_scope': 'regional_pilot', 'calendar': 'January-December; 2026 through available data',
        'warmup': 'May 1 of the preceding year, using the same regional pilot soil and management',
        'source_refs': sources + setup.source_refs,
        'assumptions': setup.assumptions_by_year[base_year].model_dump(mode='json'),
        'seasons': seasons,
    })


if __name__ == '__main__':
    main()
