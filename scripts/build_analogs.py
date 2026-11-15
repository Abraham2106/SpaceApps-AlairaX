"""Join normalized POWER, NOAA ONI and externally reviewed ET0 for analog replay."""

import argparse
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.infrastructure.cache import write_json
# Keep the existing imports used by the regional and readiness scripts.
from backend.app.intelligence.analog_pipeline import (
    SCENARIOS as SCENARIOS,
    _oni_period_end as _oni_period_end,
    _read as _read,
    build_pipeline,
    load_normalized_climate as load_normalized_climate,
    load_normalized_oni as load_normalized_oni,
    window_options as window_options,
)
from backend.app.intelligence.features import ONI_SEASONS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--climate', required=True, type=Path, nargs='+', help='Normalized POWER JSON files')
    parser.add_argument('--oni', required=True, type=Path)
    parser.add_argument('--et0', type=Path, help='External reviewed daily ET0 JSON from Justin')
    parser.add_argument('--start-mmdd', required=True)
    parser.add_argument('--end-mmdd', required=True)
    parser.add_argument('--oni-season', required=True, choices=ONI_SEASONS)
    parser.add_argument('--tracking-end-mmdd', help='Override the feature window end for Como 2026 only')
    parser.add_argument('--tracking-oni-season', choices=ONI_SEASONS)
    parser.add_argument('--as-of', required=True, type=date.fromisoformat)
    parser.add_argument('--k', type=int, default=5)
    parser.add_argument('--strong-el-nino-k', type=int, default=3,
                        help='Explicit scenario override: default 3, selected for sparse ASO strong-El-Nino history')
    parser.add_argument('--heat-threshold-c', type=float, default=35.0)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'datasets/processed/analogs')
    args = parser.parse_args(argv)
    if bool(args.tracking_end_mmdd) != bool(args.tracking_oni_season):
        parser.error('supply both tracking window options together')
    try:
        features, analogs = build_pipeline(args.climate, args.oni, et0_file=args.et0,
            start_mmdd=args.start_mmdd, end_mmdd=args.end_mmdd, oni_season=args.oni_season,
            as_of=args.as_of, k=args.k, heat_threshold_c=args.heat_threshold_c,
            strong_el_nino_k=args.strong_el_nino_k)
        if args.tracking_end_mmdd:
            tracking_features, tracking_analogs = build_pipeline(
                args.climate, args.oni, et0_file=args.et0, start_mmdd=args.start_mmdd,
                end_mmdd=args.tracking_end_mmdd, oni_season=args.tracking_oni_season,
                as_of=args.as_of, k=args.k, heat_threshold_c=args.heat_threshold_c,
                strong_el_nino_k=args.strong_el_nino_k)
            tracking = tracking_analogs['scenarios']['like_2026']
            tracking['feature_window'] = {
                'start_mmdd': args.start_mmdd, 'end_mmdd': args.tracking_end_mmdd,
                'oni_season': args.tracking_oni_season,
            }
            if tracking['status'] == 'available':
                tracking['warnings'].append(
                    f'Como 2026 compara ventanas de clima del {args.start_mmdd} al '
                    f'{args.tracking_end_mmdd} con ONI {args.tracking_oni_season}.')
            analogs['scenarios']['like_2026'] = tracking
            features['tracking_features'] = {
                **tracking['feature_window'], 'features': tracking_features['features'],
                'excluded_years': tracking_features['excluded_years'],
            }
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    write_json(args.output_dir / 'features.json', features)
    write_json(args.output_dir / 'analogos.json', analogs)
    print(f'{len(features["features"])} complete feature years; {len(features["excluded_years"])} excluded')
    for scenario, result in analogs['scenarios'].items():
        print(f'{scenario}: {result["status"]}' + (f' ({result["reason"]})' if result['status'] == 'unavailable' else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
