"""Train NASA predictors directly against observed Liberia weekly rainfall."""

import argparse
import csv
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import xgboost as xgb

from backend.app.intelligence.rainfall_features import build_examples
from scripts.calibrate_rainfall_station import observed_total
from scripts.evaluate_rainfall import evaluate, read_station
from scripts.improve_rainfall import baseline, predict, summary, train_candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--station', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('use a new experiment directory')
    args.output.mkdir(parents=True)
    climate_path = Path('outputs/molab/import/guanacaste-features.json')
    atmosphere_path = Path('datasets/processed/climate/ml-atmosphere-guanacaste.json')
    climate = json.loads(climate_path.read_bytes())
    atmosphere = json.loads(atmosphere_path.read_bytes())
    rows = build_examples({date.fromisoformat(r['date']): r for r in climate['daily']},
                          {date.fromisoformat(r['date']): r for r in atmosphere['daily']})
    station = read_station(args.station)
    labeled = []
    for row in rows:
        observed = observed_total(station, row['date'])
        if observed is not None and row['date'].year >= 1984:
            labeled.append(row | {'target': observed})
    results = []
    for objective in ('reg:absoluteerror', 'reg:squarederror'):
        candidate = {'id': f'station_{objective.split(":")[1]}', 'objective': objective,
                     'engineered': True, 'enriched': False, 'start': 1984}
        actual, predictions, references, folds = [], [], [], []
        for start, end in [(date(2014, 1, 1), date(2018, 1, 1)), (date(2018, 1, 1), date(2023, 1, 1))]:
            _, _, prediction, reference, evaluation, details = train_candidate(labeled, candidate, start, end)
            truth = [row['target'] for row in evaluation]
            folds.append({'start': str(start), 'end_exclusive': str(end), **summary(truth, prediction, reference)})
            actual.extend(truth)
            predictions.extend(prediction.tolist())
            references.extend(reference.tolist())
        result = {'candidate': candidate, 'folds': folds, **summary(actual, predictions, references)}
        results.append(result)
        print(json.dumps({'candidate': candidate['id'], 'development': result['model']}), flush=True)
    winner = min(results, key=lambda row: row['model']['mae'])
    (args.output/'selection.json').write_text(json.dumps(winner, indent=2), encoding='utf-8')
    candidate = winner['candidate']
    model, columns, prediction, reference, evaluation, details = train_candidate(
        labeled, candidate, date(2023, 1, 1), date(2026, 11, 15))
    model.save_model(args.output/'model.ubj')
    restored = xgb.Booster(params={'device': 'cpu'})
    restored.load_model(args.output/'model.ubj')
    np.testing.assert_allclose(prediction, predict(restored, columns, evaluation, candidate, reference), atol=1e-6)
    training = [r for r in labeled if r['label_end'] < date(2023, 1, 1)]
    training_medians = {str(month): float(baseline(training, [{'date': date(2023, month, 1)}])[0]) for month in range(1, 13)}
    report = {
        'selected_candidate': candidate, 'target': 'Observed Liberia station CS000078774 rainfall, next seven days',
        'publication_lag_days': 2, 'features': columns, 'monthly_training_medians': training_medians,
        'development': results, 'diagnostic_2023_2025': summary([r['target'] for r in evaluation], prediction, reference),
        'reload_verified': True, 'device': 'cpu', 'xgboost_version': xgb.__version__, **details,
        'source_hashes': {str(p): sha256(p.read_bytes()).hexdigest() for p in (args.station, climate_path, atmosphere_path, Path(__file__))},
        'limitations': ['Complete station weeks are sparse and seasonally selective after 1991.',
                        'The 2023+ station sample was already inspected. Prospective evaluation remains pending.',
                        'Predictors use revised NASA snapshots with a two-day availability assumption.'],
    }
    (args.output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    with (args.output/'predictions.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['date', 'label_end', 'actual', 'predicted', 'baseline'])
        writer.writeheader()
        for row, forecast, monthly in zip(evaluation, prediction, reference):
            writer.writerow({'date': row['date'], 'label_end': row['label_end'], 'actual': row['target'],
                             'predicted': float(forecast), 'baseline': float(monthly)})
    diagnostics, _ = evaluate(args.output/'predictions.csv', args.station)
    diagnostics['power_evaluation'] = None
    diagnostics['label_source'] = report['target']
    station_scores = diagnostics['station_evaluation']
    for section in ('all', 'nonoverlapping'):
        station_scores[section].pop('observed_power_diagnostic', None)
    for section in ('by_season', 'by_year', 'nonoverlapping_by_season'):
        for scores in station_scores[section].values():
            scores.pop('observed_power_diagnostic', None)
    (args.output/'station-evaluation.json').write_text(json.dumps(diagnostics, indent=2), encoding='utf-8')
    print(json.dumps(report['diagnostic_2023_2025']), flush=True)
    print(json.dumps(diagnostics['station_evaluation']['nonoverlapping']), flush=True)


if __name__ == '__main__':
    main()
