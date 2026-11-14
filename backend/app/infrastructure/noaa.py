"""Read ONI and RONI separately; retain overlapping three-month windows."""

import math

from backend.app.infrastructure.cache import RawCache

URLS = {
    'oni': 'https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt',
    'roni': 'https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt',
}
SEASONS = ('DJF', 'JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ')
GROWING_SEASONS = SEASONS[4:11]


def parse_enso(text: str, index: str) -> list[dict]:
    if index not in URLS:
        raise ValueError('index must be oni or roni')
    lines = [line.split() for line in text.splitlines() if line.strip()]
    if not lines or not {'SEAS', 'YR', 'ANOM'}.issubset(lines[0]):
        raise ValueError('Unrecognized NOAA header; expected SEAS YR [TOTAL] ANOM')
    columns = lines[0]
    records, seen = [], set()
    for number, values in enumerate(lines[1:], 2):
        if len(values) != len(columns):
            raise ValueError(f'Malformed NOAA row {number}')
        row = dict(zip(columns, values))
        season, year, anomaly = row['SEAS'], int(row['YR']), float(row['ANOM'])
        if season not in SEASONS or not 1800 <= year <= 2200 or not math.isfinite(anomaly):
            raise ValueError(f'Invalid NOAA row {number}')
        if (year, season) in seen:
            raise ValueError(f'Duplicate NOAA year/season: {year} {season}')
        seen.add((year, season))
        records.append({'index': index, 'year': year, 'season': season,
                        'center_month': SEASONS.index(season) + 1,
                        'fase_temporada': season if season in GROWING_SEASONS else None,
                        'anomaly_c': None if anomaly in (-999, -99.99, -99.9) else anomaly})
    if not records:
        raise ValueError('NOAA response contains no observations')
    return sorted(records, key=lambda r: (r['year'], r['center_month']))


def ingest_enso(cache: RawCache, index: str, *, refresh: bool = False, offline: bool = False) -> dict:
    if index not in URLS:
        raise ValueError('index must be oni or roni')
    body, provenance = cache.get(URLS[index], refresh=refresh, offline=offline)
    records = parse_enso(body.decode('utf-8-sig'), index)
    return {'schema_version': '0.1.0', '_mock': False, 'generado': provenance['fetched_at'],
            'source_refs': [URLS[index]], 'provenance': provenance, 'index': index,
            'units': 'degree_C_anomaly', 'records': records,
            'warnings': ['Overlapping seasonal indices are not independent monthly observations.',
                         'Latest NOAA historical revisions are not historical publication vintages; do not use for a real-time backtest.',
                         'ONI and RONI remain separate features; no values are substituted between them.']}
