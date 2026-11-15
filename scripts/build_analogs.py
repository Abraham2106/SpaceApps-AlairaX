"""Join normalized POWER, NOAA ONI and externally reviewed ET0 for analog replay."""

import argparse
from calendar import monthrange
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.infrastructure.cache import write_json
from backend.app.intelligence.analog_knn import select_scenario
from backend.app.intelligence.features import ONI_SEASONS, build_season_features

SCENARIOS = ('strong_el_nino', 'neutral', 'la_nina', 'like_2026')


def _read(path):
    path = Path(path)
    body = path.read_bytes()
    data = json.loads(body)
    if not isinstance(data, dict) or type(data.get('_mock')) is not bool:
        raise ValueError(f'{path.name}: explicit boolean _mock required')
    return data, {'file': path.name, 'sha256': sha256(body).hexdigest(),
                  'source_refs': data.get('source_refs', []),
                  'upstream_provenance': data.get('provenance')}


def _mmdd(value):
    try:
        # A non-leap reference keeps all 1981–2026 windows reproducible.
        parsed = date.fromisoformat('2001-' + value)
    except (ValueError, TypeError):
        raise ValueError('month-day must be MM-DD and cannot be February 29') from None
    return parsed.month, parsed.day


def _oni_period_end(year, season):
    center = ONI_SEASONS.index(season) + 1
    year, month = (year + 1, 1) if center == 12 else (year, center + 1)
    return date(year, month, monthrange(year, month)[1])


def load_normalized_climate(climate_files):
    """Shared file/units/zone checks and conflict-safe daily merge."""
    if not climate_files:
        raise ValueError('at least one normalized climate file is required')
    documents, provenance, days = [], [], {}
    for path in climate_files:
        data, record = _read(path)
        if not isinstance(data.get('zona'), dict) or not isinstance(data.get('days'), list):
            raise ValueError('normalized climate requires zona and days')
        if data.get('units', {}).get('precipitation_mm') != 'mm/day' or data.get('units', {}).get('tmax_c') != 'C':
            raise ValueError('normalized climate requires precipitation_mm=mm/day and tmax_c=C units')
        if documents and (data['zona'] != documents[0]['zona'] or data['_mock'] != documents[0]['_mock']):
            raise ValueError('climate files must use the same zone and mock status')
        for row in data['days']:
            day = date.fromisoformat(row['date'])
            if not 1981 <= day.year <= 2026:
                raise ValueError('climate years must be 1981–2026')
            if row.get('et0_mm') is not None:
                raise ValueError('climate ET0 must remain null; supply it only through the reviewed ET0 file')
            if day in days and days[day] != row:
                raise ValueError(f'conflicting overlapping climate rows: {day}')
            days[day] = dict(row)
        documents.append(data)
        provenance.append(record)
    return documents, provenance, days


def load_normalized_oni(oni_file, mock, oni_season):
    """Return one explicitly selected ONI period, with no RONI substitution."""
    oni, record = _read(oni_file)
    if oni['_mock'] != mock or oni.get('index') != 'oni':
        raise ValueError('ONI input must be ONI, not RONI, with the same mock status as climate')
    anomalies = {}
    for row in oni.get('records', []):
        if row.get('season') != oni_season:
            continue
        if row.get('index', 'oni') != 'oni':
            raise ValueError('RONI records cannot substitute for ONI')
        year = row['year']
        if year in anomalies and anomalies[year] != row.get('anomaly_c'):
            raise ValueError(f'conflicting ONI records for {year} {oni_season}')
        anomalies[year] = row.get('anomaly_c')
    return oni, record, anomalies


def window_options(start_mmdd, end_mmdd, oni_season, as_of, k):
    if oni_season not in ONI_SEASONS:
        raise ValueError('ONI season must be an explicit three-month period')
    first, last = _mmdd(start_mmdd), _mmdd(end_mmdd)
    if last < first:
        raise ValueError('cross-year windows are unsupported; use an explicit within-year window')
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError('k must be a positive integer')
    if not isinstance(as_of, date):
        raise ValueError('as_of must be an explicit date')
    return first, last


def build_pipeline(climate_files, oni_file, *, et0_file=None, start_mmdd,
                   end_mmdd, oni_season, as_of, k=5, weights=None, heat_threshold_c=35.0,
                   strong_el_nino_k=None, analysis_start=None):
    """Return (features document, analogs document); never synthesize missing inputs."""
    first, last = window_options(start_mmdd, end_mmdd, oni_season, as_of, k)
    if strong_el_nino_k is not None and (isinstance(strong_el_nino_k, bool) or not isinstance(strong_el_nino_k, int) or strong_el_nino_k < 1):
        raise ValueError('strong_el_nino_k must be a positive integer')
    k_by_scenario = {scenario: (strong_el_nino_k if scenario == 'strong_el_nino' and strong_el_nino_k is not None else k)
                     for scenario in SCENARIOS}
    documents, provenance, days = load_normalized_climate(climate_files)
    mock, zone = documents[0]['_mock'], documents[0]['zona']
    oni, record, anomalies = load_normalized_oni(oni_file, mock, oni_season)
    provenance.append(record)
    et0 = None
    if et0_file is not None:
        et0, record = _read(et0_file)
        provenance.append(record)
        if et0['_mock'] != mock or et0.get('zona') != zone:
            raise ValueError('reviewed ET0 must match the climate zone and mock status')
        if et0.get('reviewed') is not True or not et0.get('reviewed_by') or not et0.get('model_version'):
            raise ValueError('ET0 requires reviewed=true, reviewed_by and model_version')
        if et0.get('units') != 'mm/day' or not isinstance(et0.get('values'), dict):
            raise ValueError('ET0 requires units=mm/day and ISO-date -> ET0 values')
        if not et0.get('source_refs'):
            raise ValueError('reviewed ET0 requires source_refs')
    features, excluded = [], []
    available_years = sorted({day.year for day in days})
    for year in available_years:
        start, end = date(year, *first), date(year, *last)
        try:
            if analysis_start is not None and start < analysis_start:
                raise ValueError('requested window starts before analysis_start')
            if end > as_of:
                raise ValueError('requested window extends beyond as_of; no future climate is used')
            if _oni_period_end(year, oni_season) > as_of:
                raise ValueError('ONI period extends beyond as_of; no future index is used')
            if et0 is None:
                raise ValueError('reviewed external ET0 file unavailable; Justin must provide it')
            rows = []
            for day, row in days.items():
                if start <= day <= end:
                    rows.append(row | {'et0_mm': et0['values'].get(day.isoformat())})
            value = build_season_features(rows, year=year, start=start, end=end,
                       oni=anomalies.get(year), oni_season=oni_season, mock=mock,
                       heat_threshold_c=heat_threshold_c)
            features.append(value)
        except ValueError as error:
            excluded.append({'year': year, 'reason': str(error)})
    generated = datetime.now(timezone.utc).isoformat()
    metadata = {
        'schema_version': '0.1.0', '_mock': mock, 'generado': generated, 'zona': zone,
        'as_of': as_of.isoformat(), 'start_mmdd': start_mmdd, 'end_mmdd': end_mmdd,
        'oni_season': oni_season, 'heat_threshold_c': heat_threshold_c,
        'k_by_scenario': k_by_scenario,
        'source_refs': sorted({url for record in provenance for url in record['source_refs']}),
        'provenance': provenance,
        'warnings': list(dict.fromkeys(warning for data in documents + [oni] + ([et0] if et0 else [])
                                      for warning in data.get('warnings', []))) + [
            'Historical NOAA revisions are retrospective data, not original publication vintages.',
            'A completed ONI period does not prove it was already published at the as_of date.',
            'Climate similarity is not a forecast, causal effect or yield recommendation.',
        ],
    }
    features_doc = metadata | {'features': [feature.to_dict() for feature in features], 'excluded_years': excluded}
    tracking = next((feature for feature in features if feature.year == 2026), None)
    scenarios = {}
    for scenario in SCENARIOS:
        scenario_k = k_by_scenario[scenario]
        try:
            if et0 is None:
                raise ValueError('reviewed external ET0 unavailable; see excluded_years and request the reviewed artifact from Justin')
            if not features:
                raise ValueError('no eligible complete feature years; see excluded_years for missing data and temporal-cutoff reasons')
            result = select_scenario(features, scenario, tracking_2026=tracking, k=scenario_k, weights=weights)
            if scenario_k < 5:
                result['warnings'].append('Small analog sample: empirical quantiles are descriptive and not calibrated confidence intervals.')
            scenarios[scenario] = {'status': 'available', 'requested_k': scenario_k, 'effective_k': scenario_k, **result}
        except ValueError as error:
            scenarios[scenario] = {'status': 'unavailable', 'reason': str(error), 'k': scenario_k,
                                   'requested_k': scenario_k, 'effective_k': None}
    analogs_doc = metadata | {'scenarios': scenarios, 'excluded_years': excluded}
    return features_doc, analogs_doc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--climate', required=True, type=Path, nargs='+', help='Normalized POWER JSON files')
    parser.add_argument('--oni', required=True, type=Path)
    parser.add_argument('--et0', type=Path, help='External reviewed daily ET0 JSON from Justin')
    parser.add_argument('--start-mmdd', required=True)
    parser.add_argument('--end-mmdd', required=True)
    parser.add_argument('--oni-season', required=True, choices=ONI_SEASONS)
    parser.add_argument('--as-of', required=True, type=date.fromisoformat)
    parser.add_argument('--k', type=int, default=5)
    parser.add_argument('--strong-el-nino-k', type=int, default=3,
                        help='Explicit scenario override: default 3, selected for sparse ASO strong-El-Nino history')
    parser.add_argument('--heat-threshold-c', type=float, default=35.0)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'datasets/processed/analogs')
    args = parser.parse_args(argv)
    try:
        features, analogs = build_pipeline(args.climate, args.oni, et0_file=args.et0,
            start_mmdd=args.start_mmdd, end_mmdd=args.end_mmdd, oni_season=args.oni_season,
            as_of=args.as_of, k=args.k, heat_threshold_c=args.heat_threshold_c,
            strong_el_nino_k=args.strong_el_nino_k)
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
