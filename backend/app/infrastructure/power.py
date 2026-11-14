"""NASA POWER daily point ingestion. No ET0 or bias correction is inferred."""

from datetime import date, timedelta
import json
import math
from urllib.parse import urlencode

from backend.app.infrastructure.cache import RawCache

ENDPOINT = 'https://power.larc.nasa.gov/api/temporal/daily/point'
PARAMETERS = {
    'PRECTOTCORR': ('precipitation_mm', 'mm/day'),
    'T2M_MIN': ('tmin_c', 'C'),
    'T2M_MAX': ('tmax_c', 'C'),
    'RH2M': ('relative_humidity_pct', '%'),
    'WS2M': ('wind_speed_2m_m_s', 'm/s'),
    'ALLSKY_SFC_SW_DWN': ('solar_radiation_mj_m2_day', 'MJ/m^2/day'),
}


def power_url(latitude: float, longitude: float, start: date, end: date) -> str:
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError('invalid coordinates')
    if start < date(1981, 1, 1) or end < start:
        raise ValueError('POWER interval must begin in 1981 or later and end >= start')
    return ENDPOINT + '?' + urlencode({
        'parameters': ','.join(PARAMETERS), 'community': 'AG', 'latitude': latitude,
        'longitude': longitude, 'start': start.strftime('%Y%m%d'), 'end': end.strftime('%Y%m%d'),
        'format': 'JSON', 'time-standard': 'LST', 'units': 'metric',
    })


def _unit_factor(parameter: str, unit: str) -> float:
    normalized = unit.lower().replace(' ', '').replace('²', '^2')
    accepted = {
        'PRECTOTCORR': {'mm/day'}, 'T2M_MIN': {'c', 'degc', '°c'},
        'T2M_MAX': {'c', 'degc', '°c'}, 'RH2M': {'%'}, 'WS2M': {'m/s'},
        'ALLSKY_SFC_SW_DWN': {'mj/m^2/day', 'mj/m2/day'},
    }
    if normalized in accepted[parameter]:
        return 1.0
    if parameter == 'ALLSKY_SFC_SW_DWN' and normalized in {'kw-hr/m^2/day', 'kwh/m^2/day', 'kw-hr/m2/day', 'kwh/m2/day'}:
        return 3.6
    raise ValueError(f'Unsupported or missing POWER unit for {parameter}: {unit!r}')


def normalize_power(payload: dict, start: date, end: date, *, rain_warning_mm: float = 500) -> dict:
    if end < start or not math.isfinite(rain_warning_mm) or rain_warning_mm <= 0:
        raise ValueError('invalid interval or rain warning threshold')
    try:
        parameters = payload['properties']['parameter']
        descriptors = payload['parameters']
    except (KeyError, TypeError) as error:
        raise ValueError('Not a NASA POWER daily point response') from error
    if not any(p in parameters for p in PARAMETERS):
        raise ValueError('POWER response has no requested variables')
    # Some historical periods omit unavailable variables entirely (e.g. solar
    # radiation in 1981). Retain their dates as null, never synthesize values.
    factors = {p: _unit_factor(p, descriptors.get(p, {}).get('units', ''))
               if parameters.get(p) else 1.0 for p in PARAMETERS}
    fill_value = payload.get('header', {}).get('fill_value', -999)
    rows, issues = [], []
    current = start
    while current <= end:
        key = current.strftime('%Y%m%d')
        row = {'date': current.isoformat(), 'et0_mm': None}
        for parameter, (field, _) in PARAMETERS.items():
            raw = parameters.get(parameter, {}).get(key)
            reason = None
            if raw is None or raw == fill_value or raw == -999:
                reason = 'missing'
            elif isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
                reason = 'invalid_number'
            elif parameter not in ('T2M_MIN', 'T2M_MAX') and raw < 0:
                reason = 'negative_physical_value'
            elif parameter == 'RH2M' and raw > 100:
                reason = 'humidity_out_of_range'
            if reason:
                row[field] = None
                issues.append({'date': current.isoformat(), 'parameter': parameter, 'reason': reason})
            else:
                row[field] = raw * factors[parameter]
        if row['tmin_c'] is not None and row['tmax_c'] is not None and row['tmin_c'] > row['tmax_c']:
            row['tmin_c'] = row['tmax_c'] = None
            issues.append({'date': current.isoformat(), 'parameter': 'T2M_MIN,T2M_MAX', 'reason': 'inverted_temperature'})
        if row['precipitation_mm'] is not None and row['precipitation_mm'] > rain_warning_mm:
            issues.append({'date': current.isoformat(), 'parameter': 'PRECTOTCORR', 'reason': 'high_rainfall_review_required'})
        rows.append(row)
        current += timedelta(days=1)
    return {
        'start': start.isoformat(), 'end': end.isoformat(), 'days': rows,
        'units': {field: unit for field, unit in PARAMETERS.values()} | {'et0_mm': 'mm/day'},
        'quality_control': {'issues': issues, 'rain_warning_mm': rain_warning_mm,
                            'rain_policy': 'flag_only_no_clipping', 'bias_correction': None},
        'provider_header': payload.get('header', {}), 'provider_units': {p: descriptors.get(p, {}).get('units') for p in PARAMETERS},
        'provider_geometry': payload.get('geometry'),
    }


def ingest_power(cache: RawCache, latitude: float, longitude: float, start: date, end: date,
                 *, refresh: bool = False, offline: bool = False, rain_warning_mm: float = 500) -> dict:
    url = power_url(latitude, longitude, start, end)
    body, provenance = cache.get(url, refresh=refresh, offline=offline)
    data = normalize_power(json.loads(body), start, end, rain_warning_mm=rain_warning_mm)
    return {
        'schema_version': '0.1.0', '_mock': False, 'generado': provenance['fetched_at'],
        'zona': {'id': 'provisional-point', 'name': 'Provisional agricultural point, Guanacaste',
                 'latitude': latitude, 'longitude': longitude, 'validated': False},
        'source_refs': [url], 'provenance': provenance,
        'warnings': ['Location is provisional; SoilGrids and farm suitability are not validated.',
                     'ET0 is null until the scientific kernel calculates it.',
                     'No IMN rainfall calibration is applied; bias claims require independent validation.'],
        **data,
    }
