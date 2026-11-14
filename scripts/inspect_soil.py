"""Save real SoilGrids data or an explicit failed-attempt report."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.infrastructure.cache import RawCache, write_json
from backend.app.infrastructure.soil import DEPTHS, inspect_soil


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--latitude', type=float, default=10.55)
    parser.add_argument('--longitude', type=float, default=-85.50)
    parser.add_argument('--depth', action='append', choices=DEPTHS, help='Repeat for multiple layers; default 0-5cm')
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--raw-dir', type=Path, default=ROOT / 'datasets/raw/soil')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'datasets/processed/soil')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--refresh', action='store_true')
    group.add_argument('--offline', action='store_true')
    args = parser.parse_args(argv)
    # Two sequential calls; no automatic retries (ISRIC fair use: <=5 calls/minute).
    report = inspect_soil(RawCache(args.raw_dir, timeout=args.timeout, attempts=1), args.latitude, args.longitude,
                          tuple(args.depth or ['0-5cm']), refresh=args.refresh, offline=args.offline)
    output = args.output_dir / f'soil_readiness_{args.latitude}_{args.longitude}.json'
    write_json(output, report)
    print(f'{output}: {report["status"]}; ready_for_simulation={report["ready_for_simulation"]}')
    for attempt in report['attempts']:
        print(f'{attempt["group"]}: {attempt["status"]}' + (f' ({attempt["error_type"]}: {attempt["error"]})' if 'error' in attempt else ''))


if __name__ == '__main__':
    main()
