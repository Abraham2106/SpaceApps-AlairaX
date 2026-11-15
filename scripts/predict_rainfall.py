"""Reload an improved rainfall model and forecast from a versioned NASA snapshot."""

import argparse
from datetime import date
import json
from pathlib import Path

import pandas as pd
import xgboost as xgb

from backend.app.intelligence.rainfall_features import rainfall_features


def predict(model_dir, climate_document, atmosphere_document, origin):
    report = json.loads((model_dir / 'report.json').read_bytes())
    candidate = report['selected_candidate']
    climate = {date.fromisoformat(row['date']): row for row in climate_document['daily']}
    atmosphere = {date.fromisoformat(row['date']): row for row in atmosphere_document['daily']}
    features = rainfall_features(climate, atmosphere, origin,
                                 lag_days=report['publication_lag_days'],
                                 engineered=candidate['engineered'], enriched=candidate['enriched'])
    if features.get('rain_7d_mm') is None or all(features.get(key) is None for key in ('tmin_c', 'tmax_c')):
        raise ValueError('insufficient published climate history for this forecast origin')
    columns = report['features']
    model = xgb.Booster(params={'device': 'cpu'})
    model.load_model(model_dir / 'model.ubj')
    values = pd.DataFrame([features]).reindex(columns=columns).astype('float32')
    prediction = max(0.0, float(model.predict(xgb.DMatrix(values))[0]))
    if candidate.get('dry_baseline') and origin.month in (12, 1, 2, 3, 4):
        prediction = report['monthly_training_medians'][str(origin.month)]
    return {'origin': origin.isoformat(), 'horizon_days': 7,
            'precipitation_mm': prediction, 'candidate': candidate['id'],
            'target': report.get('target', 'NASA POWER grid-cell rainfall, next seven days'),
            'publication_lag_days': report['publication_lag_days'],
            'interpretation': 'Retrospective forecast from supplied snapshots. Verify publication timestamps before operational issuance.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--climate', type=Path, required=True)
    parser.add_argument('--atmosphere', type=Path, required=True)
    parser.add_argument('--origin', type=date.fromisoformat, required=True)
    args = parser.parse_args()
    print(json.dumps(predict(args.model_dir, json.loads(args.climate.read_bytes()),
                             json.loads(args.atmosphere.read_bytes()), args.origin), indent=2))


if __name__ == '__main__':
    main()
