"""Audit saved rainfall predictions against POWER and a GHCN daily station."""

import argparse
from calendar import monthrange
from collections import defaultdict
import csv
from datetime import date, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import mean

STATION_ID = 'CS000078774'


def read_station(path):
    """Keep PRCP in mm with blank QFLAG. Missing days remain absent."""
    daily = {}
    for number, line in enumerate(path.read_text(encoding='ascii').splitlines(), 1):
        if len(line) < 269:
            raise ValueError(f'truncated GHCN row {number}')
        if line[:11] != STATION_ID:
            raise ValueError('expected the Liberia station')
        if line[17:21] != 'PRCP':
            continue
        year, month = int(line[11:15]), int(line[15:17])
        for day in range(1, monthrange(year, month)[1] + 1):
            start = 21 + 8 * (day - 1)
            value = int(line[start:start + 5])
            measurement, quality = line[start + 5:start + 7]
            # B/D concern precipitation assembled from hourly totals.
            # Preserve only daily records and traces (reported as zero).
            if value < 0 or quality != ' ' or measurement in ('B', 'D'):
                continue
            current = date(year, month, day)
            if current in daily:
                raise ValueError(f'duplicate station date {current}')
            daily[current] = value / 10
    return daily


def score(rows, target, prediction):
    if not rows:
        return None
    errors = [row[prediction] - row[target] for row in rows]
    absolute = [abs(error) for error in errors]
    return {
        'n': len(rows), 'mae_mm': mean(absolute),
        'rmse_mm': math.sqrt(mean(error * error for error in errors)),
        'bias_mm': mean(errors),
        'within_10mm_pct': 100 * mean(error <= 10 for error in absolute),
    }


def summarize(rows, target):
    columns = [('xgboost', 'predicted'), ('monthly_median', 'baseline')]
    if target == 'station_mm':
        columns.append(('observed_power_diagnostic', 'actual'))
    return {name: score(rows, target, column) for name, column in columns}


def grouped(rows, target, group_by):
    groups = defaultdict(list)
    for row in rows:
        groups[group_by(row)].append(row)
    return {str(key): summarize(group, target) for key, group in sorted(groups.items())}


def season(row):
    return 'wet_may_nov' if 5 <= row['date'].month <= 11 else 'dry_dec_apr'


def nonoverlapping(rows):
    selected, previous_end = [], date.min
    for row in sorted(rows, key=lambda item: item['date']):
        if row['date'] + timedelta(days=1) > previous_end:
            selected.append(row)
            previous_end = row['label_end']
    return selected


def evaluate(predictions_path, station_path):
    station = read_station(station_path)
    with predictions_path.open(encoding='utf-8', newline='') as source:
        rows = list(csv.DictReader(source))
    for row in rows:
        row['date'] = date.fromisoformat(row['date'])
        row['label_end'] = date.fromisoformat(row['label_end'])
        if row['label_end'] != row['date'] + timedelta(days=7):
            raise ValueError('expected seven-day prediction horizons')
        for name in ('actual', 'predicted', 'baseline'):
            row[name] = float(row[name])
            if not math.isfinite(row[name]) or row[name] < 0:
                raise ValueError('expected finite nonnegative rainfall')
    if len({row['date'] for row in rows}) != len(rows):
        raise ValueError('duplicate forecast origins')
    paired = []
    for row in rows:
        days = [row['date'] + timedelta(days=step) for step in range(1, 8)]
        if all(day in station for day in days):
            paired.append(row | {'station_mm': sum(station[day] for day in days)})
    weekly = nonoverlapping(paired)
    return {
        'schema_version': 1,
        'prediction_sha256': sha256(predictions_path.read_bytes()).hexdigest(),
        'station_sha256': sha256(station_path.read_bytes()).hexdigest(),
        'station_id': STATION_ID,
        'station_coordinates': {'latitude': 10.6, 'longitude': -85.533},
        'quality_rule': 'PRCP >= 0, blank QFLAG, exclude MFLAG B/D, all seven daily records required',
        'power_evaluation': {
            'all': summarize(rows, 'actual'),
            'by_season': grouped(rows, 'actual', season),
            'by_year': grouped(rows, 'actual', lambda row: row['date'].year),
        },
        'station_evaluation': {
            'paired_windows': len(paired), 'excluded_windows': len(rows) - len(paired),
            'all': summarize(paired, 'station_mm'),
            'by_season': grouped(paired, 'station_mm', season),
            'by_year': grouped(paired, 'station_mm', lambda row: row['date'].year),
            'nonoverlapping': summarize(weekly, 'station_mm'),
            'nonoverlapping_by_season': grouped(weekly, 'station_mm', season),
        },
        'limitations': [
            'Observed station rainfall and POWER grid rainfall describe different spatial supports.',
            'Daily observing periods may differ between GHCN and POWER local solar time.',
            'Retrospective predictor snapshots do not establish a real-time forecasting result.',
            'Station missingness restricts the sample and can bias the evaluation.',
            'Overlapping daily seven-day targets are dependent. Nonoverlapping windows are also weather-correlated.',
            'The POWER test set has already been inspected. Treat it as development evidence.',
        ],
    }, paired


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--station', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report, paired = evaluate(args.predictions, args.station)
    csv_path = args.output.with_suffix('.paired.csv')
    if {args.output.resolve(), csv_path.resolve()} & {args.predictions.resolve(), args.station.resolve()}:
        parser.error('outputs must differ from source files')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if paired:
        with csv_path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=paired[0])
            writer.writeheader()
            writer.writerows(paired)
    print(json.dumps(report['station_evaluation'], indent=2))


if __name__ == '__main__':
    main()
