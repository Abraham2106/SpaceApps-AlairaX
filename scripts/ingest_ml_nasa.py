"""Download public NASA POWER atmospheric predictors with immutable raw caching."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import json
from pathlib import Path

from backend.app.infrastructure.cache import RawCache, write_json

PARAMETERS = {'PS': 'kPa', 'T2MDEW': 'C', 'QV2M': 'g/kg', 'PW': 'cm',
              'U2M': 'm/s', 'V2M': 'm/s'}
OUTPUT = Path('datasets/processed/climate/ml-atmosphere-guanacaste.json')


def fetch_year(year):
    end = f'{year}1231' if year < 2026 else '20261114'
    url = ('https://power.larc.nasa.gov/api/temporal/daily/point?'
           f'parameters={",".join(PARAMETERS)}&community=AG&latitude=10.55&longitude=-85.5'
           f'&start={year}0101&end={end}&format=JSON&time-standard=LST')
    body, provenance = RawCache('datasets/raw/ml-nasa', timeout=45, attempts=2).get(url)
    data = json.loads(body)
    for key, units in PARAMETERS.items():
        if data['parameters'][key]['units'] != units:
            raise ValueError(f'{key}: unexpected source unit')
    values = data['properties']['parameter']
    if set(values) != set(PARAMETERS):
        raise ValueError('unexpected NASA variable set')
    rows = []
    for day in sorted(set().union(*(values[key] for key in PARAMETERS))):
        current = date(int(day[:4]), int(day[4:6]), int(day[6:]))
        row = {'date': current.isoformat()}
        for key in PARAMETERS:
            value = values[key].get(day)
            row[key] = None if value in (None, -999, -9999) else value
        rows.append(row)
    print(f'{year}: {len(rows)} days', flush=True)
    return rows, provenance


def main():
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(fetch_year, range(2005, 2027)))
    document = {
        '_mock': False, 'latitude': 10.55, 'longitude': -85.5, 'time_standard': 'LST',
        'generated_at': datetime.now(timezone.utc).isoformat(), 'units': PARAMETERS,
        'provenance': [record for _, record in results],
        'daily': [row for rows, _ in results for row in rows],
        'availability_assumption_days': 2,
        'warnings': ['Historical snapshots are revised retrospective data. Actual publication time must be checked for live forecasts.'],
    }
    write_json(OUTPUT, document)


if __name__ == '__main__':
    main()
