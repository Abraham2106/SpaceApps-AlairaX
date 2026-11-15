from datetime import date, timedelta

import pytest

from backend.app.intelligence.rainfall_features import build_examples, rainfall_features


def climate_rows():
    start = date(2020, 1, 1)
    return {start + timedelta(days=i): {
        'precipitation_mm': float(i % 9), 'tmin_c': 20, 'tmax_c': 30,
        'relative_humidity_pct': 70, 'wind_speed_2m_m_s': 2,
    } for i in range(120)}


def test_future_weather_and_unpublished_days_cannot_change_features():
    climate = climate_rows()
    origin = date(2020, 4, 10)
    cutoff = origin - timedelta(days=2)
    atmosphere = {day: {'PS': 100, 'PW': 4, 'QV2M': 15, 'T2MDEW': 22,
                       'U2M': 1, 'V2M': -1} for day in climate}
    expected = rainfall_features(climate, atmosphere, origin, enriched=True)
    for day in climate:
        if day > cutoff:
            climate[day] = {key: 9999 for key in climate[day]}
            atmosphere[day] = {key: 9999 for key in atmosphere[day]}
    assert rainfall_features(climate, atmosphere, origin, enriched=True) == expected
    assert expected['rain_1d_mm'] == climate[cutoff]['precipitation_mm']
    assert expected['PW'] == 4


def test_missing_rain_is_preserved_in_rolling_features():
    climate = climate_rows()
    origin = date(2020, 4, 10)
    climate[origin - timedelta(days=3)]['precipitation_mm'] = None
    features = rainfall_features(climate, {}, origin)
    assert features['rain_3d_mm'] is None
    assert features['wet_days_3d'] is None
    assert features['rain_7d_mm'] is None
    assert features['rain_1d_mm'] is not None


def test_target_uses_future_rain_after_forecast_origin():
    climate = climate_rows()
    row = next(row for row in build_examples(climate, {}) if row['date'] == date(2020, 4, 10))
    assert row['target'] == sum(climate[row['date'] + timedelta(days=i)]['precipitation_mm'] for i in range(1, 8))
    assert row['label_end'] == row['date'] + timedelta(days=7)
    with pytest.raises(ValueError):
        rainfall_features(climate, {}, row['date'], lag_days=-1)
