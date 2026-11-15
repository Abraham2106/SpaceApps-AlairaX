"""Causal daily predictors for a seven-day rainfall target with publication lag."""

from datetime import date, timedelta
from math import cos, isfinite, pi, sin
from statistics import fmean, pstdev

WEATHER = ('tmin_c', 'tmax_c', 'relative_humidity_pct', 'wind_speed_2m_m_s')
ATMOSPHERE = ('PS', 'T2MDEW', 'QV2M', 'PW', 'U2M', 'V2M')


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value not in (-999, -9999)


def rainfall_features(daily, atmosphere, origin, *, lag_days=2, engineered=True, enriched=False):
    if lag_days < 0:
        raise ValueError('publication lag cannot be negative')
    cutoff = origin - timedelta(days=lag_days)
    history = lambda n: [daily.get(cutoff - timedelta(days=i), {}) for i in range(n)]
    features = {'month': origin.month}
    row = daily.get(cutoff, {})
    features.update({key: row.get(key) if finite(row.get(key)) else None for key in WEATHER})
    for n in (7, 15, 30, 90):
        rain = [r.get('precipitation_mm') for r in history(n)]
        features[f'rain_{n}d_mm'] = sum(rain) if all(finite(v) and v >= 0 for v in rain) else None
    if not engineered:
        return features
    angle = 2 * pi * (origin.timetuple().tm_yday - 1) / 365.25
    features.update(doy_sin=sin(angle), doy_cos=cos(angle),
                    doy_sin_2=sin(2 * angle), doy_cos_2=cos(2 * angle))
    for n in (1, 3, 7, 14, 30):
        rain = [r.get('precipitation_mm') for r in history(n)]
        valid = all(finite(v) and v >= 0 for v in rain)
        features[f'rain_{n}d_mm'] = sum(rain) if valid else None
        features[f'wet_days_{n}d'] = sum(v >= 1 for v in rain) if valid else None
        if n >= 7:
            features[f'rain_max_{n}d_mm'] = max(rain) if valid else None
            features[f'rain_sd_{n}d_mm'] = pstdev(rain) if valid else None
    dry = 0
    for prior in history(30):
        value = prior.get('precipitation_mm')
        if not finite(value):
            dry = None
            break
        if value >= 1:
            break
        dry += 1
    features['dry_spell_capped_30d'] = dry
    for key in WEATHER:
        for n in (3, 7):
            values = [r.get(key) for r in history(n)]
            features[f'{key}_mean_{n}d'] = fmean(values) if all(finite(v) for v in values) else None
    if finite(row.get('tmax_c')) and finite(row.get('tmin_c')):
        features['temperature_range_c'] = row['tmax_c'] - row['tmin_c']
    if enriched:
        for key in ATMOSPHERE:
            values = [atmosphere.get(cutoff - timedelta(days=i), {}).get(key) for i in range(7)]
            features[key] = values[0] if finite(values[0]) else None
            features[f'{key}_mean_7d'] = fmean(values) if all(finite(v) for v in values) else None
            features[f'{key}_change_3d'] = values[0] - values[3] if finite(values[0]) and finite(values[3]) else None
    return features


def build_examples(climate, atmosphere, *, engineered=True, enriched=False, lag_days=2):
    rows = []
    for origin in sorted(climate):
        future = [climate.get(origin + timedelta(days=i), {}).get('precipitation_mm') for i in range(1, 8)]
        if not all(finite(v) and v >= 0 for v in future):
            continue
        rows.append({
            'date': origin, 'label_end': origin + timedelta(days=7),
            'features': rainfall_features(climate, atmosphere, origin, lag_days=lag_days,
                                         engineered=engineered, enriched=enriched),
            'target': sum(future),
        })
    return rows
