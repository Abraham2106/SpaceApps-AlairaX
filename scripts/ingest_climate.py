"""Download explicit date ranges, cache raw responses, export normalized JSON."""

import argparse
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.infrastructure.cache import RawCache, write_json
from backend.app.infrastructure.noaa import ingest_enso
from backend.app.infrastructure.power import ingest_power


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', required=True, type=date.fromisoformat, help='YYYY-MM-DD')
    parser.add_argument('--end', required=True, type=date.fromisoformat, help='YYYY-MM-DD')
    parser.add_argument('--latitude', type=float, default=10.55)
    parser.add_argument('--longitude', type=float, default=-85.50)
    parser.add_argument('--raw-dir', type=Path, default=ROOT / 'datasets/raw/climate')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'datasets/processed/climate')
    parser.add_argument('--rain-warning-mm', type=float, default=500)
    parser.add_argument('--skip-noaa', action='store_true')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--refresh', action='store_true', help='Fetch new snapshots while retaining old raw bodies')
    group.add_argument('--offline', action='store_true', help='Use cached responses only')
    args = parser.parse_args(argv)
    cache = RawCache(args.raw_dir)
    options = {'refresh': args.refresh, 'offline': args.offline}
    # Annual chunks keep full-history downloads resumable without concurrent requests.
    cursor = args.start
    if args.end < cursor:
        parser.error('--end must be >= --start')
    while cursor <= args.end:
        chunk_end = min(args.end, date(cursor.year, 12, 31))
        result = ingest_power(cache, args.latitude, args.longitude, cursor, chunk_end,
                              rain_warning_mm=args.rain_warning_mm, **options)
        name = f'power_{args.latitude}_{args.longitude}_{cursor}_{chunk_end}.json'
        write_json(args.output_dir / name, result)
        print(f'{name}: {len(result["days"])} days; {len(result["quality_control"]["issues"])} QC flags')
        if chunk_end == args.end:
            break
        cursor = date(cursor.year + 1, 1, 1)
    if not args.skip_noaa:
        for index in ('oni', 'roni'):
            result = ingest_enso(cache, index, **options)
            write_json(args.output_dir / f'{index}.json', result)
            print(f'{index}.json: {len(result["records"])} seasonal observations')


if __name__ == '__main__':
    main()
