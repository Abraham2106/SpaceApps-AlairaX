from datetime import date, datetime, timedelta
import json

from scripts import ingest_forecast_comparison as ingestion


def test_ecmwf_seven_whole_utc_dates_exclude_initial_day(tmp_path, monkeypatch):
    origin = date(2024, 6, 1)
    times = [(datetime(2024, 6, 1) + timedelta(hours=i)).isoformat(timespec='minutes') for i in range(216)]
    body = {
        'latitude': 10.58, 'longitude': -85.48,
        'hourly_units': {'precipitation': 'mm'},
        'hourly': {'time': times, 'precipitation': [100 if stamp.startswith('2024-06-01') else 1 for stamp in times]},
    }
    monkeypatch.setattr(ingestion, 'RAW', tmp_path)
    monkeypatch.setattr(ingestion, 'request', lambda *args: (json.dumps(body).encode(), {}))
    result = ingestion.ecmwf(origin)
    assert result['daily_mm'] == [24] * 7
    assert result['precipitation_mm'] == 168


def test_missing_hour_leaves_forecast_total_unknown(tmp_path, monkeypatch):
    times = [(datetime(2024, 6, 1) + timedelta(hours=i)).isoformat(timespec='minutes') for i in range(216)]
    rain = [1] * len(times)
    rain[30] = None
    body = {'latitude': 10.58, 'longitude': -85.48, 'hourly_units': {'precipitation': 'mm'},
            'hourly': {'time': times, 'precipitation': rain}}
    monkeypatch.setattr(ingestion, 'RAW', tmp_path)
    monkeypatch.setattr(ingestion, 'request', lambda *args: (json.dumps(body).encode(), {}))
    result = ingestion.ecmwf(date(2024, 6, 1))
    assert result['daily_mm'][0] is None
    assert result['precipitation_mm'] is None
