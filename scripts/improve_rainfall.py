"""Bounded, nested temporal validation of causal NASA rainfall features."""

import argparse
from collections import defaultdict
import csv
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import monotonic

import numpy as np
import pandas as pd
import xgboost as xgb

from backend.app.intelligence.rainfall_features import build_examples
from scripts.train_molab import metrics

CANDIDATES = [
    {'id': 'basic_all', 'engineered': False, 'enriched': False, 'start': 1984, 'objective': 'reg:squarederror'},
    {'id': 'engineered_all', 'engineered': True, 'enriched': False, 'start': 1984, 'objective': 'reg:absoluteerror'},
    {'id': 'engineered_recent', 'engineered': True, 'enriched': False, 'start': 2005, 'objective': 'reg:absoluteerror'},
    {'id': 'nasa_recent_mae', 'engineered': True, 'enriched': True, 'start': 2005, 'objective': 'reg:absoluteerror'},
    {'id': 'nasa_recent_mse', 'engineered': True, 'enriched': True, 'start': 2005, 'objective': 'reg:squarederror'},
    {'id': 'nasa_seasonal', 'engineered': True, 'enriched': True, 'start': 2005, 'objective': 'reg:absoluteerror', 'dry_baseline': True},
]
FOLDS = [('2014-01-01', '2018-01-01'), ('2018-01-01', '2023-01-01')]


def frame(rows, columns=None):
    values = pd.DataFrame([row['features'] for row in rows])
    if columns is not None:
        values = values.reindex(columns=columns)
    return values.astype('float32')


def baseline(training, evaluation):
    months = defaultdict(list)
    for row in training:
        months[row['date'].month].append(row['target'])
    fallback = median(row['target'] for row in training)
    return np.array([median(months[row['date'].month]) if months[row['date'].month] else fallback
                     for row in evaluation])


def fit(training, validation, candidate, rounds=800):
    columns = sorted(training[0]['features'])
    train_matrix = xgb.DMatrix(frame(training, columns), label=[r['target'] for r in training])
    params = {'objective': candidate['objective'], 'tree_method': 'hist', 'device': 'cpu',
              'eval_metric': 'mae', 'max_depth': 3, 'eta': 0.03, 'min_child_weight': 20,
              'lambda': 10, 'subsample': 0.85, 'colsample_bytree': 0.85, 'seed': 42, 'nthread': 4}
    history = {}
    started = monotonic()

    class Deadline(xgb.callback.TrainingCallback):
        def after_iteration(self, model, epoch, evals_log):
            return monotonic() - started >= 30

    evals = [(train_matrix, 'train')]
    callbacks = [Deadline()]
    if validation:
        evals.append((xgb.DMatrix(frame(validation, columns), label=[r['target'] for r in validation]), 'validation'))
        callbacks.append(xgb.callback.EarlyStopping(rounds=40, metric_name='mae',
                                                    data_name='validation', maximize=False))
    model = xgb.train(params, train_matrix, num_boost_round=rounds, evals=evals,
                      callbacks=callbacks, evals_result=history, verbose_eval=False)
    if validation:
        model = model[:int(np.argmin(history['validation']['mae'])) + 1]
    return model, columns, history, params


def predict(model, columns, rows, candidate, climatology):
    prediction = np.maximum(0, model.predict(xgb.DMatrix(frame(rows, columns))))
    if candidate.get('dry_baseline'):
        prediction = np.where([r['date'].month in (12, 1, 2, 3, 4) for r in rows], climatology, prediction)
    return prediction


def train_candidate(rows, candidate, start, end):
    # Purge labels crossing both the inner and outer time boundaries.
    tuning_start = date(start.year - 2, 1, 1)
    training = [r for r in rows if r['label_end'] < start]
    inner_train = [r for r in training if r['label_end'] < tuning_start]
    inner_valid = [r for r in training if r['date'] >= tuning_start]
    evaluation = [r for r in rows if start <= r['date'] < end and r['label_end'] < end]
    if not inner_train or not inner_valid or not evaluation:
        raise ValueError('insufficient data for nested temporal validation')
    tuned, _, tuning_history, _ = fit(inner_train, inner_valid, candidate)
    model, columns, history, params = fit(training, [], candidate, rounds=tuned.num_boosted_rounds())
    reference = baseline(training, evaluation)
    predictions = predict(model, columns, evaluation, candidate, reference)
    return model, columns, predictions, reference, evaluation, {
        'rounds': model.num_boosted_rounds(), 'parameters': params,
        'training_count': len(training), 'inner_validation_count': len(inner_valid),
        'tuning_history': tuning_history, 'refit_history': history,
    }


def summary(actual, prediction, reference):
    return {'model': metrics(actual, prediction, 10), 'baseline': metrics(actual, reference, 10)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--climate', type=Path, default=Path('outputs/molab/import/guanacaste-features.json'))
    parser.add_argument('--atmosphere', type=Path, default=Path('datasets/processed/climate/ml-atmosphere-guanacaste.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('use a new output directory to preserve experiments')
    args.output.mkdir(parents=True)
    climate_document = json.loads(args.climate.read_bytes())
    atmosphere_document = json.loads(args.atmosphere.read_bytes())
    if climate_document['_mock'] or atmosphere_document['_mock']:
        raise ValueError('real NASA inputs required')
    climate = {date.fromisoformat(r['date']): r for r in climate_document['daily']}
    atmosphere = {date.fromisoformat(r['date']): r for r in atmosphere_document['daily']}
    if len(climate) != len(climate_document['daily']) or len(atmosphere) != len(atmosphere_document['daily']):
        raise ValueError('duplicate source dates')
    results, datasets = [], {}
    for candidate in CANDIDATES:
        rows = build_examples(climate, atmosphere, engineered=candidate['engineered'],
                              enriched=candidate['enriched'], lag_days=2)
        rows = [r for r in rows if r['date'].year >= candidate['start']]
        datasets[candidate['id']] = rows
        folds, predictions, actual, references = [], [], [], []
        for start, end in FOLDS:
            _, _, prediction, reference, evaluation, details = train_candidate(
                rows, candidate, date.fromisoformat(start), date.fromisoformat(end))
            truth = [r['target'] for r in evaluation]
            folds.append({'start': start, 'end_exclusive': end, **summary(truth, prediction, reference),
                          'rounds': details['rounds']})
            predictions.extend(prediction.tolist())
            actual.extend(truth)
            references.extend(reference.tolist())
        result = {'candidate': candidate, 'folds': folds, **summary(actual, predictions, references)}
        results.append(result)
        (args.output/'development.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(candidate['id'], 'development MAE', result['model']['mae'], flush=True)
    winner = min(results, key=lambda result: result['model']['mae'])
    candidate = winner['candidate']
    # Selection is complete before looking at the already-inspected 2023+ period.
    (args.output/'selection.json').write_text(json.dumps(winner, indent=2), encoding='utf-8')
    model, columns, prediction, reference, evaluation, details = train_candidate(
        datasets[candidate['id']], candidate, date(2023, 1, 1), date(2026, 11, 15))
    model.save_model(args.output/'model.ubj')
    restored = xgb.Booster(params={'device': 'cpu'})
    restored.load_model(args.output/'model.ubj')
    np.testing.assert_allclose(prediction, predict(restored, columns, evaluation, candidate, reference),
                               atol=1e-6)
    with (args.output/'predictions.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['date', 'label_end', 'actual', 'predicted', 'baseline'])
        writer.writeheader()
        for row, forecast, monthly in zip(evaluation, prediction, reference):
            writer.writerow({'date': row['date'], 'label_end': row['label_end'],
                             'actual': row['target'], 'predicted': float(forecast), 'baseline': float(monthly)})
    training = [r for r in datasets[candidate['id']] if r['label_end'] < date(2023, 1, 1)]
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(), 'selected_candidate': candidate,
        'selection_rule': 'Minimum pooled outer validation MAE on 2014-2017 and 2018-2022. Inner time validation selects rounds.',
        'publication_lag_days': 2, 'features': columns, 'rounds': details['rounds'],
        'monthly_training_medians': {month: median(r['target'] for r in training if r['date'].month == month) for month in range(1, 13)},
        'development': results, 'diagnostic_2023_2026': summary([r['target'] for r in evaluation], prediction, reference),
        'limitations': ['2023-2026 has been inspected in earlier experiments and is a development diagnostic.',
                        'Two-day lag approximates POWER meteorological latency. Real-time historical publication vintages are unavailable.',
                        'Target remains grid-cell NASA POWER precipitation. Local station validation is separate.'],
        'source_hashes': {str(p): sha256(p.read_bytes()).hexdigest() for p in (args.climate, args.atmosphere, Path(__file__))},
        'feature_code_sha256': sha256(Path('backend/app/intelligence/rainfall_features.py').read_bytes()).hexdigest(),
        'xgboost_version': xgb.__version__, 'device': 'cpu', 'reload_verified': True, **details,
    }
    (args.output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Selected', candidate['id'], report['diagnostic_2023_2026'], flush=True)


if __name__ == '__main__':
    main()
