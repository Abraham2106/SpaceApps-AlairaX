"""Probe SoilGrids availability without equating texture to hydraulic capacity."""

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from backend.app.infrastructure.cache import RawCache, write_json

ENDPOINT = 'https://rest.isric.org/soilgrids/v2.0/properties/query'
TEXTURE = ('clay', 'sand', 'silt')
RETENTION = ('wv0010', 'wv0033', 'wv1500')
DEPTHS = ('0-5cm', '5-15cm', '15-30cm', '30-60cm', '60-100cm', '100-200cm')


def soil_url(latitude: float, longitude: float, properties: tuple[str, ...], depths: tuple[str, ...]) -> str:
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError('Invalid coordinates')
    if not properties or any(p not in TEXTURE + RETENTION for p in properties):
        raise ValueError('Unknown or empty SoilGrids property selection')
    if not depths or any(d not in DEPTHS for d in depths):
        raise ValueError('Unknown or empty SoilGrids depth selection')
    return ENDPOINT + '?' + urlencode({'lon': longitude, 'lat': latitude, 'property': properties,
                                       'depth': depths, 'value': 'mean'}, doseq=True)


def normalize_soil(payload: dict, properties: tuple[str, ...], depths: tuple[str, ...]) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get('properties'), dict):
        raise ValueError('Not a SoilGrids properties object')
    layers = payload['properties'].get('layers')
    if not isinstance(layers, list):
        raise ValueError('Not a SoilGrids properties response: layers are missing')
    by_name = {layer['name']: layer for layer in layers if isinstance(layer, dict) and 'name' in layer}
    result = []
    for name in properties:
        layer = by_name.get(name, {})
        measure = layer.get('unit_measure', {})
        mapped = measure.get('mapped_units')
        # Conversion is based on mapped units, never the API display divisor alone.
        # Texture mapped g/kg -> percent; water mapped 0.001 volume fraction -> m3/m3.
        factor, unit = None, None
        if name in TEXTURE and mapped == 'g/kg':
            factor, unit = .1, 'percent_mass'
        if name in RETENTION and mapped in ('10^-3 cm^3/cm^3', '10-3 cm3/cm3', '0.1 v%', '1 mm/m', 'cm3/dm3',
                                            '(10-2 cm³/cm³)*10'):
            factor, unit = .001, 'm3/m3'
        by_depth = {item.get('label'): item for item in layer.get('depths', [])}
        for depth in depths:
            item = by_depth.get(depth, {})
            raw = item.get('values', {}).get('mean')
            reason = None
            if raw is None:
                reason = 'provider_no_value'
            elif isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) or raw < 0:
                reason = 'invalid_provider_value'
            elif factor is None:
                reason = 'unit_requires_review'
            elif raw * factor > (100 if name in TEXTURE else 1):
                reason = 'normalized_value_out_of_range'
            safe_raw = raw if not isinstance(raw, float) or math.isfinite(raw) else None
            result.append({'property': name, 'depth': depth, 'statistic': 'mean', 'raw_value': safe_raw,
                           'provider_unit_measure': measure, 'value': raw * factor if reason is None else None,
                           'unit': unit, 'reason': reason, 'depth_range': item.get('range')})
    return result


def inspect_soil(cache: RawCache, latitude: float = 10.55, longitude: float = -85.50,
                 depths: tuple[str, ...] = ('0-5cm',), *, refresh: bool = False, offline: bool = False) -> dict:
    attempts, values = [], []
    for group, properties in (('texture', TEXTURE), ('water_retention', RETENTION)):
        url = soil_url(latitude, longitude, properties, depths)
        evidence = {'group': group, 'url': url, 'attempted_at': datetime.now(timezone.utc).isoformat()}
        try:
            body, provenance = cache.get(url, refresh=refresh, offline=offline)
            evidence['provenance'] = provenance
            normalized = normalize_soil(json.loads(body), properties, depths)
            values.extend(normalized)
            evidence.update({'status': 'response_received', 'available_values': sum(v['value'] is not None for v in normalized)})
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            evidence.update({'status': 'unavailable', 'error_type': type(error).__name__, 'error': str(error),
                             'http_status': error.code if isinstance(error, HTTPError) else None})
            if isinstance(error, HTTPError):
                # Failed HTTP response bodies are evidence, never valid cached data.
                body = error.read()
                digest = sha256(body).hexdigest()
                cache.directory.mkdir(parents=True, exist_ok=True)
                (cache.directory / f'{digest}.error.body').write_bytes(body)
                evidence['error_body_sha256'] = digest
        attempts.append(evidence)
        attempt_key = sha256((url + evidence['attempted_at']).encode()).hexdigest()
        write_json(cache.directory / f'{attempt_key}.attempt.json', evidence)
    refs = [attempt['url'] for attempt in attempts if attempt['status'] == 'response_received']
    return {
        'schema_version': '0.1.0', '_mock': False, 'generado': datetime.now(timezone.utc).isoformat(),
        'zona': {'id': 'provisional-point', 'name': 'Provisional agricultural point, Guanacaste',
                 'latitude': latitude, 'longitude': longitude, 'validated': False},
        'status': 'partial' if any(v['value'] is not None for v in values) else 'blocked',
        'ready_for_simulation': False, 'requested_depths': depths, 'attempts': attempts, 'properties': values,
        'soil_profile': {'field_capacity_m3_m3': None, 'wilting_point_m3_m3': None,
                         'rooting_depth_m': None, 'source_refs': refs},
        'source_refs': refs,
        'readiness_reasons': [
            'The farm location remains provisional; a soil value does not validate agricultural land use.',
            'No field-capacity or wilting-point values are inferred from texture.',
            'Retention at 10/33/1500 kPa needs scientific review before assigning kernel FC/WP.',
            'Crop rooting depth and depth aggregation need a documented, reviewed parameter set.',
            'One surface-layer probe does not represent the root-zone profile.',
        ],
    }
