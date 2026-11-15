"""Reload the v3 experiment and predict from a saved forecast pair."""

import argparse
from datetime import date
import json
from pathlib import Path

import xgboost as xgb

from scripts.train_forecast_blend import forecast_features, predict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--forecasts', type=Path, required=True)
    parser.add_argument('--climate', type=Path, required=True)
    parser.add_argument('--origin', type=date.fromisoformat, required=True)
    args = parser.parse_args()
    report = json.loads((args.model_dir/'report.json').read_bytes())
    records = json.loads(args.forecasts.read_bytes())['records']
    record = next(row for row in records if row['origin'] == str(args.origin))
    climate = {date.fromisoformat(row['date']): row
               for row in json.loads(args.climate.read_bytes())['daily']}
    ecmwf = record['ecmwf']['precipitation_mm']
    chirps = record['chirps_gefs']['precipitation_mm']
    values = {'ecmwf': ecmwf, 'chirps_gefs': chirps, 'mean_forecasts': (ecmwf+chirps)/2,
              'monthly': report['monthly_utc_training_medians'][str(args.origin.month)]}
    model = xgb.Booster(params={'device': 'cpu'})
    model.load_model(args.model_dir/'residual-model.ubj')
    values['xgboost_residual'] = float(predict(model, report['feature_schema'],
                                            [{'features': forecast_features(record, climate),
                                              'ecmwf': ecmwf}])[0])
    selected = values[report['selected']]
    band = report['empirical_error_band']['half_width_mm']
    print(json.dumps({'origin': str(args.origin), 'target': report['target'],
                      'selected': report['selected'], 'predicted_mm': selected,
                      'candidates_mm': values,
                      'empirical_lower_mm': max(0, selected-band) if band is not None else None,
                      'empirical_upper_mm': selected+band if band is not None else None,
                      'status': 'Retrospective experiment; regional grid target, pending prospective farm validation.'}, indent=2))


if __name__ == '__main__':
    main()
