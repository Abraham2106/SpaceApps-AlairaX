"""Compare archived weather forecasts and fit a bounded residual XGBoost model."""

import argparse
import csv
from datetime import date, timedelta
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
from statistics import mean, median

import numpy as np
import pandas as pd
import xgboost as xgb

from backend.app.intelligence.rainfall_features import finite, rainfall_features
from scripts.evaluate_rainfall import nonoverlapping, read_station, score, season


def forecast_features(record, climate):
    origin = date.fromisoformat(record['origin'])
    ecmwf = record['ecmwf']['precipitation_mm']
    chirps = record['chirps_gefs']['precipitation_mm']
    features = rainfall_features(climate, {}, origin)
    features.update(ecmwf_mm=ecmwf, chirps_gefs_mm=chirps,
                    forecast_difference_mm=ecmwf-chirps)
    features.update({f'forecast_{key}': value for key, value in record['ecmwf'].get('weather', {}).items()})
    for key in ('ecmwf', 'chirps_gefs'):
        daily = record[key]['daily_mm']
        features[f'{key}_maximum_day_mm'] = max(daily)
        features[f'{key}_wet_days'] = sum(v >= 1 for v in daily)
    return features


def forecast_rows(document, climate, previous, utc_rainfall, monthly):
    rows = []
    for record in document['records']:
        origin = date.fromisoformat(record['origin'])
        values = [utc_rainfall.get(str(origin + timedelta(days=i))) for i in range(1, 8)]
        ecmwf = record.get('ecmwf', {}).get('precipitation_mm')
        chirps = record.get('chirps_gefs', {}).get('precipitation_mm')
        if not all(finite(v) and v >= 0 for v in values + [ecmwf, chirps]) or origin not in previous:
            continue
        features = forecast_features(record, climate)
        rows.append({
            'date': origin, 'label_end': origin + timedelta(days=7), 'actual': sum(values),
            'ecmwf': ecmwf, 'chirps_gefs': chirps, 'mean_forecasts': (ecmwf+chirps)/2,
            'previous_v2': previous[origin]['predicted'], 'monthly': monthly[origin.month],
            'features': features,
        })
    return sorted(rows, key=lambda row: row['date'])


def fit(rows):
    columns = sorted(rows[0]['features'])
    frame = pd.DataFrame([row['features'] for row in rows]).reindex(columns=columns).astype('float32')
    matrix = xgb.DMatrix(frame, label=[row['actual'] - row['ecmwf'] for row in rows])
    parameters = {'objective': 'reg:absoluteerror', 'tree_method': 'hist', 'device': 'cpu',
                  'max_depth': 2, 'eta': 0.03, 'min_child_weight': 10, 'lambda': 10,
                  'subsample': 0.85, 'colsample_bytree': 0.85, 'seed': 42, 'nthread': 4}
    return xgb.train(parameters, matrix, num_boost_round=150), columns, parameters


def predict(model, columns, rows):
    frame = pd.DataFrame([row['features'] for row in rows]).reindex(columns=columns).astype('float32')
    return np.maximum(0, model.predict(xgb.DMatrix(frame)) + [row['ecmwf'] for row in rows])


def summarize(rows, column):
    result = score(rows, 'actual', column)
    if result:
        errors = sorted(abs(row['actual'] - row[column]) for row in rows)
        result['within_20mm_pct'] = 100 * mean(error <= 20 for error in errors)
        result['median_absolute_error_mm'] = median(errors)
        result['p90_absolute_error_mm'] = errors[ceil(0.9*len(errors))-1]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forecasts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--utc-rainfall', type=Path,
                        default=Path('datasets/processed/climate/power-utc-rainfall-2005-2025.json'))
    args = parser.parse_args()
    if args.output.exists():
        parser.error('use a new directory to preserve the experiment')
    climate_path = Path('outputs/molab/import/guanacaste-features.json')
    previous_path = Path('outputs/molab/nasa-features-v2/predictions.csv')
    climate = {date.fromisoformat(row['date']): row for row in json.loads(climate_path.read_bytes())['daily']}
    with previous_path.open(newline='', encoding='utf-8') as handle:
        previous = {date.fromisoformat(row['date']): {key: float(row[key]) for key in ('predicted', 'baseline')}
                    for row in csv.DictReader(handle)}
    document = json.loads(args.forecasts.read_bytes())
    utc_document = json.loads(args.utc_rainfall.read_bytes())
    if utc_document['time_standard'] != 'UTC' or utc_document['units'] != 'mm/day':
        raise ValueError('UTC daily rainfall labels in mm/day required')
    utc_values = utc_document['values']
    monthly_values = {month: [] for month in range(1, 13)}
    for origin in (date.fromisoformat(day) for day in sorted(utc_values)):
        if origin + timedelta(days=7) >= date(2024, 1, 1):
            continue
        rain = [utc_values.get(str(origin + timedelta(days=i))) for i in range(1, 8)]
        if all(finite(v) and v >= 0 for v in rain):
            monthly_values[origin.month].append(sum(rain))
    monthly = {month: median(values) for month, values in monthly_values.items()}
    rows = forecast_rows(document, climate, previous, utc_values, monthly)
    splits = {
        'train': [r for r in rows if r['label_end'] < date(2024, 8, 1)],
        'selection': [r for r in rows if date(2024, 8, 1) <= r['date'] and r['label_end'] < date(2024, 10, 1)],
        'calibration': [r for r in rows if date(2024, 10, 1) <= r['date'] and r['label_end'] < date(2025, 1, 1)],
        'diagnostic': [r for r in rows if r['date'] >= date(2025, 1, 1)],
    }
    if any(not group for group in splits.values()):
        raise ValueError('all temporal partitions require complete forecast pairs')
    args.output.mkdir(parents=True)
    model, columns, parameters = fit(splits['train'])
    # Restrict selection to non-overlapping verification weeks.
    selection = nonoverlapping(splits['selection'])
    for row, value in zip(selection, predict(model, columns, selection)):
        row['xgboost_residual'] = float(value)
    candidates = ['monthly', 'previous_v2', 'ecmwf', 'chirps_gefs', 'mean_forecasts', 'xgboost_residual']
    selection_scores = {key: summarize(selection, key) for key in candidates}
    selected = min((key for key in candidates if key != 'previous_v2'),
                   key=lambda key: selection_scores[key]['mae_mm'])
    (args.output/'selection.json').write_text(json.dumps({'selected': selected, 'scores': selection_scores}, indent=2), encoding='utf-8')
    training = splits['train'] + splits['selection']
    model, columns, parameters = fit(training)
    model.save_model(args.output/'residual-model.ubj')
    restored = xgb.Booster(params={'device': 'cpu'})
    restored.load_model(args.output/'residual-model.ubj')
    for group in ('calibration', 'diagnostic'):
        predictions = predict(model, columns, splits[group])
        np.testing.assert_allclose(predictions, predict(restored, columns, splits[group]), atol=1e-6)
        for row, value in zip(splits[group], predictions):
            row['xgboost_residual'] = float(value)
            row['selected'] = row[selected]
    calibration = nonoverlapping(splits['calibration'])
    errors = sorted(abs(row['actual'] - row['selected']) for row in calibration)
    rank = ceil((len(errors)+1)*0.9)
    band = errors[rank-1] if rank <= len(errors) else None
    diagnostic = nonoverlapping(splits['diagnostic'])
    for row in diagnostic:
        row['lower_mm'] = max(0, row['selected'] - band) if band is not None else None
        row['upper_mm'] = row['selected'] + band if band is not None else None
    station = read_station(Path('outputs/molab/field-validation/liberia.dly'))
    paired_days = [{'date': str(day), 'power_utc_mm': utc_values[str(day)], 'station_mm': observed,
                    'absolute_difference_mm': abs(utc_values[str(day)]-observed)}
                   for day, observed in station.items()
                   if day >= date(2024, 1, 1) and finite(utc_values.get(str(day)))]
    local = []
    for row in splits['diagnostic']:
        dates = [row['date'] + timedelta(days=i) for i in range(1, 8)]
        if all(day in station for day in dates):
            local.append(row | {'actual': sum(station[day] for day in dates)})
    local = nonoverlapping(local)
    report = {
        'selected': selected, 'selection_scores': selection_scores,
        'split_counts_all': {key: len(group) for key, group in splits.items()},
        'split_counts_nonoverlapping': {key: len(nonoverlapping(group)) for key, group in splits.items()},
        'diagnostic_power': {key: summarize(diagnostic, key) for key in candidates},
        'diagnostic_station': {key: summarize(local, key) for key in candidates},
        'selected_by_season': {key: summarize([r for r in diagnostic if season(r) == key], 'selected')
                               for key in ('dry_dec_apr', 'wet_may_nov')},
        'empirical_error_band': {
            'nominal_coverage': 0.9, 'calibration_n': len(errors), 'half_width_mm': band,
            'diagnostic_coverage_pct': 100*mean(r['lower_mm'] <= r['actual'] <= r['upper_mm'] for r in diagnostic) if band is not None else None,
            'interpretation': 'Empirical nominal 90% band; time dependence and distribution shifts limit coverage guarantees.',
            'operationally_validated': False,
        },
        'label_quality_audit': {
            'paired_station_days': len(paired_days),
            'largest_daily_grid_station_discrepancies': sorted(
                paired_days, key=lambda row: row['absolute_difference_mm'], reverse=True)[:10],
            'interpretation': 'Grid-cell and nearby point observations have different spatial support and observing-day boundaries. Large discrepancies require independent corroboration; no automatic label deletion.',
        },
        'feature_schema': columns, 'parameters': parameters, 'rounds': 150, 'reload_verified': True,
        'monthly_utc_training_medians': monthly,
        'model_training_n': len(training), 'source_forecast_warnings': document['warnings'],
        'source_hashes': {str(path): sha256(path.read_bytes()).hexdigest()
                          for path in (args.forecasts, climate_path, previous_path, args.utc_rainfall, Path(__file__))},
        'target': 'NASA POWER seven-day UTC rainfall total',
        'limitations': [
            '2025 outcomes were inspected in previous experiments. These results are retrospective diagnostics.',
            'Primary forecasts and labels use UTC calendar days. Station observing periods can differ.',
            'Previous v2 was trained on LST targets and is an approximate legacy reference, excluded from model selection.',
            'CHIRPS3-GEFS historical rasters were reprocessed after the original dates.',
            'Only 2024-2025 forecast samples are used, and local station weeks are sparse.',
            'Extreme POWER daily totals disagree with nearby station readings; the primary target is not validated farm rainfall.',
            'The calibration band is experimental and must not be used to automate irrigation.',
        ],
    }
    (args.output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    with (args.output/'predictions.csv').open('w', newline='', encoding='utf-8') as handle:
        keys = ['date', 'label_end', 'actual', *candidates, 'selected', 'lower_mm', 'upper_mm']
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(diagnostic)
    print(json.dumps({'selected': selected, 'diagnostic': summarize(diagnostic, 'selected'),
                      'band': report['empirical_error_band'], 'local': summarize(local, 'selected')}, indent=2))


if __name__ == '__main__':
    main()
