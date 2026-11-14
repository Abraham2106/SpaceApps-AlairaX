"""Inspect climate/ONI coverage before ET0; this report never runs KNN."""

import argparse
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.infrastructure.cache import write_json
from backend.app.infrastructure.power import PARAMETERS
from backend.app.intelligence.features import ONI_SEASONS
from scripts.build_analogs import (
    SCENARIOS, _oni_period_end, load_normalized_climate, load_normalized_oni, window_options,
)


def _valid_number(value):
    return not isinstance(value, bool) and isinstance(value, (float, int)) and isfinite(value) and value != -999


def inspect_scenarios(climate_files, oni_file, *, start_mmdd, end_mmdd, oni_season,
                      as_of, k=5, strong_el_nino_k=None):
    first, last = window_options(start_mmdd, end_mmdd, oni_season, as_of, k)
    if strong_el_nino_k is not None and (isinstance(strong_el_nino_k, bool) or not isinstance(strong_el_nino_k, int) or strong_el_nino_k < 1):
        raise ValueError('strong_el_nino_k must be a positive integer')
    documents, provenance, days = load_normalized_climate(climate_files)
    mock, zone = documents[0]['_mock'], documents[0]['zona']
    oni, record, anomalies = load_normalized_oni(oni_file, mock, oni_season)
    provenance.append(record)
    units = {field: unit for field, unit in PARAMETERS.values()}
    for document in documents:
        if any(document.get('units', {}).get(field) != unit for field, unit in units.items()):
            raise ValueError('readiness requires all six normalized POWER unit declarations')
    years = []
    for year in sorted({day.year for day in days}):
        start, end = date(year, *first), date(year, *last)
        expected = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        missing_dates, invalid = [], {field: 0 for field in units}
        inverted_temperature_days = 0
        for day in expected:
            row = days.get(day)
            if row is None:
                missing_dates.append(day.isoformat())
                continue
            for field in units:
                value = row.get(field)
                valid = _valid_number(value)
                if valid and field not in ('tmin_c', 'tmax_c'):
                    valid = value >= 0
                if valid and field == 'relative_humidity_pct':
                    valid = value <= 100
                if not valid:
                    invalid[field] += 1
            if _valid_number(row.get('tmin_c')) and _valid_number(row.get('tmax_c')) and row['tmin_c'] > row['tmax_c']:
                inverted_temperature_days += 1
        climate_complete = not missing_dates and not any(invalid.values()) and not inverted_temperature_days
        anomaly = anomalies.get(year)
        oni_valid = _valid_number(anomaly) and anomaly not in (-99.99, -99.9)
        cutoff_complete = end <= as_of and _oni_period_end(year, oni_season) <= as_of
        reasons = []
        if missing_dates:
            reasons.append('missing climate dates')
        if any(invalid.values()):
            reasons.append('missing or invalid six-variable climate values')
        if inverted_temperature_days:
            reasons.append('inverted daily temperature bounds')
        if not oni_valid:
            reasons.append('selected ONI period unavailable or invalid')
        if not cutoff_complete:
            reasons.append('climate window or ONI period extends beyond as_of')
        years.append({'year': year, 'start': start.isoformat(), 'end': end.isoformat(),
                      'oni_anomaly_c': anomaly, 'oni_period_end': _oni_period_end(year, oni_season).isoformat(),
                      'six_input_climate_complete': climate_complete, 'oni_valid': oni_valid,
                      'within_information_cutoff': cutoff_complete,
                      'climate_oni_eligible_before_et0': climate_complete and oni_valid and cutoff_complete,
                      'et0_reviewed': False, 'missing_climate_dates': missing_dates,
                      'invalid_days_by_field': invalid, 'inverted_temperature_days': inverted_temperature_days,
                      'reasons': reasons})
    history = [row for row in years if row['year'] <= 2025 and row['climate_oni_eligible_before_et0']]
    tracking = next((row for row in years if row['year'] == 2026), None)
    predicates = {
        'strong_el_nino': (lambda value: value >= 1.5, 'seasonal ONI >= 1.5 C'),
        'neutral': (lambda value: -0.5 < value < 0.5, '-0.5 C < seasonal ONI < 0.5 C'),
        'la_nina': (lambda value: value <= -0.5, 'seasonal ONI <= -0.5 C'),
        'like_2026': (lambda value: True, 'all historical years matching the observed tracking window'),
    }
    scenarios = {}
    k_by_scenario = {scenario: strong_el_nino_k if scenario == 'strong_el_nino' and strong_el_nino_k is not None else k for scenario in SCENARIOS}
    for scenario in SCENARIOS:
        predicate, rule = predicates[scenario]
        selected = [row for row in history if predicate(row['oni_anomaly_c'])]
        target_exists = scenario != 'like_2026' or bool(tracking and tracking['climate_oni_eligible_before_et0'])
        supports_k = len(selected) >= k_by_scenario[scenario]
        status = 'blocked_pending_reviewed_et0'
        if not target_exists:
            status = 'tracking_climate_oni_unavailable'
        elif not supports_k:
            status = 'insufficient_climate_oni_years'
        scenarios[scenario] = {
            'status': status, 'phase_rule': rule, 'requested_k': k_by_scenario[scenario],
            'effective_k': None, 'climate_oni_count_before_et0': len(selected),
            'candidate_years_before_et0': [row['year'] for row in selected],
            'climate_oni_supports_requested_k': supports_k, 'tracking_window_complete': target_exists,
            'knn_has_run': False, 'et0_reviewed': False,
            'warnings': ['This is coverage readiness, not a KNN result or ET0 readiness.'] +
                        (['Small analog sample: quantiles remain descriptive and are not confidence intervals.'] if k_by_scenario[scenario] < 5 else []),
        }
    return {
        'schema_version': '0.1.0', '_mock': mock, 'generado': datetime.now(timezone.utc).isoformat(),
        'zona': zone, 'start_mmdd': start_mmdd, 'end_mmdd': end_mmdd, 'oni_season': oni_season,
        'as_of': as_of.isoformat(), 'k_by_scenario': k_by_scenario,
        'report_kind': 'six_input_climate_and_oni_coverage_before_et0',
        'knn_has_run': False, 'et0_reviewed': False, 'provenance': provenance,
        'source_refs': sorted({url for item in provenance for url in item['source_refs']}),
        'historical_climate_oni_count_before_et0': len(history), 'years': years,
        'scenarios': scenarios,
        'warnings': [
            'Six complete POWER inputs do not certify ET0, soil, crop parameters or kernel readiness.',
            'Current NOAA revisions are retrospective data, not original publication vintages.',
            'A period ending before as_of does not establish its actual publication date.',
            'Seasonal ONI buckets are product rules, not sustained NOAA ENSO event classifications.',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--climate', type=Path, nargs='+', required=True)
    parser.add_argument('--oni', type=Path, required=True)
    parser.add_argument('--start-mmdd', required=True)
    parser.add_argument('--end-mmdd', required=True)
    parser.add_argument('--oni-season', choices=ONI_SEASONS, required=True)
    parser.add_argument('--as-of', type=date.fromisoformat, required=True)
    parser.add_argument('--k', type=int, default=5)
    parser.add_argument('--strong-el-nino-k', type=int, default=3)
    parser.add_argument('--output', type=Path, default=ROOT / 'datasets/processed/readiness/scenarios.json')
    args = parser.parse_args(argv)
    try:
        report = inspect_scenarios(args.climate, args.oni, start_mmdd=args.start_mmdd,
                    end_mmdd=args.end_mmdd, oni_season=args.oni_season, as_of=args.as_of,
                    k=args.k, strong_el_nino_k=args.strong_el_nino_k)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    write_json(args.output, report)
    print(f'{report["historical_climate_oni_count_before_et0"]} historical climate/ONI years before reviewed ET0')
    for scenario, result in report['scenarios'].items():
        print(f'{scenario}: {result["climate_oni_count_before_et0"]} candidate years before ET0; requested k={result["requested_k"]}; {result["status"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
