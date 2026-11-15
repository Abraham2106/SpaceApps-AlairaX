"""Fit a small local correction using out-of-time station residuals only."""

import argparse
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
from statistics import median

from backend.app.intelligence.rainfall_features import build_examples
from scripts.evaluate_rainfall import evaluate, read_station
from scripts.improve_rainfall import train_candidate
from scripts.train_molab import metrics
import csv


def observed_total(station, origin):
    days = [origin + timedelta(days=i) for i in range(1, 8)]
    return sum(station[d] for d in days) if all(d in station for d in days) else None


def coefficients(rows):
    residuals = {}
    for wet in (True, False):
        subset = [row for row in rows if (5 <= row['date'].month <= 11) == wet]
        residuals[str(wet)] = median(row['actual'] - row['predicted'] for row in subset) if subset else 0
    return residuals


def correction(value, origin, offsets):
    return max(0.0, value + offsets[str(5 <= origin.month <= 11)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--station', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads((args.model_dir / 'report.json').read_bytes())
    candidate = report['selected_candidate']
    climate = json.loads(Path('outputs/molab/import/guanacaste-features.json').read_bytes())
    atmosphere = json.loads(Path('datasets/processed/climate/ml-atmosphere-guanacaste.json').read_bytes())
    rows = build_examples({date.fromisoformat(r['date']): r for r in climate['daily']},
                          {date.fromisoformat(r['date']): r for r in atmosphere['daily']},
                          engineered=candidate['engineered'], enriched=candidate['enriched'])
    rows = [r for r in rows if r['date'].year >= candidate['start']]
    station = read_station(args.station)
    folds = []
    for start, end in [(date(2014, 1, 1), date(2018, 1, 1)), (date(2018, 1, 1), date(2023, 1, 1))]:
        _, _, prediction, _, evaluation, _ = train_candidate(rows, candidate, start, end)
        paired = []
        for row, value in zip(evaluation, prediction):
            target = observed_total(station, row['date'])
            if target is not None:
                paired.append({'date': row['date'], 'actual': target, 'predicted': float(value)})
        folds.append(paired)
    training, validation = folds
    if not training or not validation:
        raise ValueError('local calibration requires complete station weeks in both development blocks')
    offsets = coefficients(training)
    truth = [r['actual'] for r in validation]
    raw = metrics(truth, [r['predicted'] for r in validation], 10)
    corrected = metrics(truth, [correction(r['predicted'], r['date'], offsets) for r in validation], 10)
    use_correction = corrected['mae'] < raw['mae']
    final_offsets = coefficients(training + validation) if use_correction else {'True': 0, 'False': 0}
    calibration = {
        'target': 'Liberia CS000078774 observed weekly rainfall',
        'method': 'seasonal median residual from out-of-time predictions' if use_correction else 'identity',
        'development_training_windows': len(training), 'development_validation_windows': len(validation),
        'selection_period': '2018-2022', 'fit_period': 'out-of-time forecasts 2014-2022',
        'validation_uncorrected': raw, 'validation_corrected': corrected,
        'seasonal_offsets_mm': final_offsets,
        'unsupported_seasons': [str(wet) for wet in (True, False) if not any((5 <= r['date'].month <= 11) == wet for r in training + validation)],
        'station_file_sha256': sha256(args.station.read_bytes()).hexdigest(),
        'limitations': ['Sparse station coverage can bias correction.', 'Day boundaries and point-to-grid differences remain.'],
    }
    (args.model_dir / 'station-calibration.json').write_text(json.dumps(calibration, indent=2), encoding='utf-8')
    with (args.model_dir / 'predictions.csv').open(newline='', encoding='utf-8') as handle:
        predictions = list(csv.DictReader(handle))
    for row in predictions:
        row['predicted'] = correction(float(row['predicted']), date.fromisoformat(row['date']), final_offsets)
    path = args.model_dir / 'station-calibrated-predictions.csv'
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=predictions[0])
        writer.writeheader()
        writer.writerows(predictions)
    evaluation, _ = evaluate(path, args.station)
    (args.model_dir / 'station-calibrated-evaluation.json').write_text(json.dumps(evaluation, indent=2), encoding='utf-8')
    print(json.dumps(calibration, indent=2), flush=True)
    print(json.dumps(evaluation['station_evaluation']['nonoverlapping'], indent=2), flush=True)


if __name__ == '__main__':
    main()
