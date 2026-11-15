"""Bounded XGBoost training for regional forecasts and FAO-56 surrogates."""

import argparse
from collections import defaultdict
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from time import monotonic
from uuid import uuid4

import numpy as np
import pandas as pd

RAIN_FEATURES = ('rain_7d_mm', 'rain_15d_mm', 'rain_30d_mm', 'rain_90d_mm',
                 'tmin_c', 'tmax_c', 'relative_humidity_pct', 'wind_speed_2m_m_s',
                 'solar_radiation_mj_m2_day')


def rainfall_examples(document):
    daily = {date.fromisoformat(row['date']): row for row in document['daily']}
    if len(daily) != len(document['daily']):
        raise ValueError('duplicate daily dates')
    rows = []
    for cutoff, row in sorted(daily.items()):
        dates = [cutoff + timedelta(days=n) for n in range(1, 8)]
        rain = [daily.get(day, {}).get('precipitation_mm') for day in dates]
        if any(value is None for value in rain):
            continue
        features = {key: row.get(key) for key in RAIN_FEATURES}
        features['month'] = cutoff.month
        rows.append({'date': cutoff, 'label_end': dates[-1], 'features': features, 'target': sum(rain)})
    return rows


def surrogate_examples(document, target):
    if document.get('task') != 'simulator_surrogate':
        raise ValueError('expected a simulator surrogate dataset')
    rows = []
    for row in document['rows']:
        if row['label_source'] != 'simulation' or row['features'].keys() & row['labels'].keys():
            raise ValueError('expected simulated labels kept separate from model features')
        year = row['climate_year']
        rows.append({'date': date(year, 1, 1),
                     # Backward compatibility for existing exports of May–April seasons.
                     'label_end': date.fromisoformat(row['replay_end']) if 'replay_end' in row else date(year+1, 4, 30),
                     'features': row['features'], 'target': row['labels'][target]})
    return rows


def split_rows(rows, validation_start, test_start):
    if validation_start >= test_start:
        raise ValueError('validation_start must precede test_start')
    splits = {'train': [], 'validation': [], 'test': []}
    purged = 0
    for row in rows:
        if any(row['date'] < boundary <= row['label_end'] for boundary in (validation_start, test_start)):
            purged += 1
            continue
        split = 'test' if row['date'] >= test_start else 'validation' if row['date'] >= validation_start else 'train'
        splits[split].append(row)
    if any(not group for group in splits.values()):
        raise ValueError('all three time partitions must contain examples after removing boundary overlaps')
    return splits, purged


def frames(splits):
    raw = {name: pd.DataFrame([row['features'] for row in rows]) for name, rows in splits.items()}
    train = raw['train']
    categorical = [key for key in train if train[key].dtype == 'object' and train[key].notna().any()]
    numeric = [key for key in train if key not in categorical and train[key].notna().any()]
    vocabularies = {key: sorted(train[key].dropna().unique().tolist()) for key in categorical}
    return {name: encode(frame, numeric, vocabularies) for name, frame in raw.items()}, numeric, vocabularies


def encode(frame, numeric, vocabularies):
    encoded = frame.reindex(columns=numeric).astype('float32')
    for key, values in vocabularies.items():
        series = frame[key] if key in frame else pd.Series(index=frame.index, dtype=object)
        for index, value in enumerate(values):
            encoded[f'{key}__{index}'] = series.eq(value).astype('float32')
    return encoded


def metrics(actual, predicted, tolerance):
    errors = np.abs(np.asarray(actual) - np.asarray(predicted))
    return {'n': len(errors), 'mae': float(errors.mean()), 'rmse': float(np.sqrt(np.mean(errors**2))),
            'within_tolerance_pct': float(100*np.mean(errors <= tolerance))}


def train(path, output_root, *, task, validation_start, test_start, rounds=500, patience=40,
          tolerance=10.0, seconds=600, device='cuda', target='modeled_water_deficit_mm'):
    import xgboost as xgb

    if not (0 < rounds <= 10000 and 0 < patience and 0 < seconds and np.isfinite(tolerance) and tolerance >= 0):
        raise ValueError('invalid round, time or tolerance limits')
    if device not in ('cuda', 'cpu') or task not in ('rainfall', 'surrogate'):
        raise ValueError('invalid device or task')
    hardware = 'CPU'
    if device == 'cuda':
        hardware = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader'], text=True, timeout=15).strip()
        if not xgb.build_info().get('USE_CUDA') or '6000 Blackwell' not in hardware:
            raise RuntimeError(f'RTX PRO 6000 Blackwell and CUDA-enabled XGBoost required. Detected {hardware}')

    body = Path(path).read_bytes()
    document = json.loads(body)
    rows = rainfall_examples(document) if task == 'rainfall' else surrogate_examples(document, target)
    splits, purged = split_rows(rows, validation_start, test_start)
    data, numeric, vocabularies = frames(splits)
    labels = {name: np.array([row['target'] for row in group]) for name, group in splits.items()}
    if any(not np.isfinite(y).all() for y in labels.values()):
        raise ValueError('targets must be finite')
    matrices = {name: xgb.DMatrix(data[name], label=labels[name], nthread=4) for name in data}
    evals = [(matrices['train'], 'train'), (matrices['validation'], 'validation')]
    params = {'device': device, 'tree_method': 'hist', 'objective': 'reg:squarederror',
              'eval_metric': 'mae', 'max_depth': 4, 'eta': .05, 'seed': 42, 'nthread': 4}
    started = monotonic()

    class TimeLimit(xgb.callback.TrainingCallback):
        def after_iteration(self, model, epoch, evals_log):
            return monotonic() - started >= seconds

    history = {}
    def tolerance_metric(predictions, matrix):
        error = np.abs(matrix.get_label() - np.maximum(0, predictions))
        return 'within_tolerance_pct', float(100*np.mean(error <= tolerance))

    stop = xgb.callback.EarlyStopping(rounds=patience, metric_name='mae',
                                      data_name='validation', maximize=False)
    model = xgb.train(params, matrices['train'], num_boost_round=rounds, evals=evals,
                      callbacks=[stop, TimeLimit()], custom_metric=tolerance_metric,
                      evals_result=history, verbose_eval=False)
    observed = json.loads(model.save_config())['learner']['generic_param']['device']
    if device == 'cuda' and not observed.startswith('cuda'):
        raise RuntimeError('XGBoost did not execute with CUDA')
    best = int(np.argmin(history['validation']['mae'])) + 1
    selected = model[:best]
    run_dir = Path(output_root) / uuid4().hex
    run_dir.mkdir(parents=True)
    selected.save_model(run_dir/'model.ubj')
    restored = xgb.Booster(params={'device': device})
    restored.load_model(run_dir/'model.ubj')
    prediction = np.maximum(0, selected.predict(matrices['test']))
    np.testing.assert_allclose(prediction, np.maximum(0, restored.predict(matrices['test'])), atol=1e-6)
    monthly = defaultdict(list)
    for row in splits['train']:
        monthly[row['date'].month].append(row['target'])
    median = float(np.median(labels['train']))
    baseline = [float(np.median(monthly[row['date'].month]))
                if task == 'rainfall' and monthly[row['date'].month] else median for row in splits['test']]
    by_year = defaultdict(list)
    for index, row in enumerate(splits['test']):
        by_year[row['date'].year].append(index)
    report = {
        'task': task, 'target': 'rain_next_7d_mm' if task == 'rainfall' else target,
        'label_source': 'NASA POWER gridded rainfall' if task == 'rainfall' else 'FAO-56 simulation',
        '_mock': document.get('_mock'), 'data_sha256': sha256(body).hexdigest(),
        'trainer_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'hardware': hardware, 'device': observed, 'xgboost_version': xgb.__version__, 'parameters': params,
        'validation_start': validation_start.isoformat(), 'test_start': test_start.isoformat(),
        'tolerance': tolerance, 'round_limit': rounds, 'patience': patience, 'seconds_limit': seconds,
        'split_counts': {name: len(group) for name, group in splits.items()}, 'purged_rows': purged,
        'best_round': best, 'test': metrics(labels['test'], prediction, tolerance),
        'baseline': metrics(labels['test'], baseline, tolerance),
        'test_by_year': {year: metrics(labels['test'][idx], prediction[idx], tolerance)
                         for year, idx in sorted(by_year.items())},
        'numeric_features': numeric, 'categorical_vocabulary': vocabularies,
        'reload_verified': True,
    }
    for name, obj in [('report', report), ('history', history)]:
        (run_dir/f'{name}.json').write_text(json.dumps(obj, indent=2), encoding='utf-8')
    pd.DataFrame({'date': [row['date'] for row in splits['test']],
                  'label_end': [row['label_end'] for row in splits['test']],
                  'actual': labels['test'], 'predicted': prediction,
                  'baseline': baseline}).to_csv(run_dir/'predictions.csv', index=False)
    return run_dir, report, history


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--output', default=Path('outputs/molab'), type=Path)
    parser.add_argument('--task', choices=['rainfall', 'surrogate'], default='rainfall')
    parser.add_argument('--validation-start', type=date.fromisoformat, required=True)
    parser.add_argument('--test-start', type=date.fromisoformat, required=True)
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    parser.add_argument('--rounds', type=int, default=500)
    parser.add_argument('--patience', type=int, default=40)
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--tolerance', type=float, default=10)
    parser.add_argument('--target', choices=['modeled_water_deficit_mm', 'crop_water_demand_mm',
                                             'water_stress_days'], default='modeled_water_deficit_mm')
    args = parser.parse_args()
    directory, report, _ = train(args.dataset, args.output, task=args.task,
        validation_start=args.validation_start, test_start=args.test_start,
        device=args.device, rounds=args.rounds, patience=args.patience,
        seconds=args.seconds, tolerance=args.tolerance, target=args.target)
    print(directory)
    print(json.dumps({'best_round': report['best_round'], 'test': report['test'], 'baseline': report['baseline']}))
