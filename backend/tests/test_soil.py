"""Missing/unsupported soil evidence must never become hydraulic parameters."""

from unittest.mock import Mock
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse

from backend.app.api.schemas.contracts import SoilProfile
from backend.app.infrastructure.cache import RawCache
from backend.app.infrastructure.soil import TEXTURE, inspect_soil, normalize_soil, soil_url


def layer(name, value, unit):
    return {'name': name, 'unit_measure': {'mapped_units': unit, 'd_factor': 10},
            'depths': [{'label': '0-5cm', 'range': {'top_depth': 0, 'bottom_depth': 5, 'unit_depth': 'cm'},
                        'values': {'mean': value}}]}


class SoilTests(unittest.TestCase):
    def test_url_uses_repeated_properties_and_depths(self):
        query = parse_qs(urlparse(soil_url(10.55, -85.5, TEXTURE, ('0-5cm', '5-15cm'))).query)
        self.assertEqual(query['property'], ['clay', 'sand', 'silt'])
        self.assertEqual(query['depth'], ['0-5cm', '5-15cm'])

    def test_texture_conversion_keeps_missing_values_null(self):
        payload = {'properties': {'layers': [layer('clay', 350, 'g/kg'), layer('sand', None, 'g/kg')]}}
        values = normalize_soil(payload, TEXTURE, ('0-5cm',))
        self.assertEqual(values[0]['value'], 35)
        self.assertEqual(values[0]['unit'], 'percent_mass')
        self.assertIsNone(values[1]['value'])
        self.assertIsNone(values[2]['value'])

    def test_retention_unit_conversion_is_fraction_not_percent(self):
        payload = {'properties': {'layers': [layer('wv1500', 130, '10^-3 cm^3/cm^3')]}}
        value = normalize_soil(payload, ('wv1500',), ('0-5cm',))[0]
        self.assertEqual(value['value'], .13)
        self.assertEqual(value['unit'], 'm3/m3')

    def test_unknown_units_do_not_get_guessed(self):
        payload = {'properties': {'layers': [layer('wv1500', 13, 'mystery_unit')]}}
        value = normalize_soil(payload, ('wv1500',), ('0-5cm',))[0]
        self.assertIsNone(value['value'])
        self.assertEqual(value['reason'], 'unit_requires_review')

    def test_invalid_payload_rejected(self):
        for payload in (None, [], {}, {'properties': None}, {'properties': {'layers': None}}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                normalize_soil(payload, TEXTURE, ('0-5cm',))

    def test_http_error_retains_actual_body_without_data(self):
        from io import BytesIO
        from pathlib import Path
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as folder:
            cache = RawCache(folder, attempts=1)
            cache.get = Mock(side_effect=lambda *args, **kwargs: (_ for _ in ()).throw(
                HTTPError(args[0], 503, 'Service unavailable', {}, BytesIO(b'actual upstream error'))))
            result = inspect_soil(cache)
            self.assertEqual(result['status'], 'blocked')
            self.assertEqual(result['attempts'][0]['http_status'], 503)
            self.assertTrue(result['attempts'][0]['error_body_sha256'])
            bodies = list(Path(folder).glob('*.error.body'))
            self.assertEqual(bodies[0].read_bytes(), b'actual upstream error')

    def test_live_failure_is_reported_as_failure_not_mock_data(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = RawCache(folder, attempts=1)
            cache.get = Mock(side_effect=TimeoutError('The read operation timed out'))
            result = inspect_soil(cache)
            self.assertFalse(result['_mock'])
            self.assertEqual(result['status'], 'blocked')
            self.assertEqual(len(result['attempts']), 2)
            self.assertEqual(result['attempts'][0]['error_type'], 'TimeoutError')
            self.assertEqual(result['source_refs'], [])
            self.assertIsNone(SoilProfile.model_validate(result['soil_profile']).field_capacity_m3_m3)
            self.assertFalse(result['zona']['validated'])

    def test_texture_success_does_not_create_fc_wp_or_rooting_depth(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            cache = RawCache(folder, attempts=1)
            payload = {'properties': {'layers': [layer('clay', 350, 'g/kg')]}}
            cache.get = Mock(return_value=(json.dumps(payload).encode(), {'sha256': 'fixture', 'fetched_at': '2026-11-14T00:00:00Z'}))
            result = inspect_soil(cache)
            self.assertEqual(result['status'], 'partial')
            self.assertFalse(result['ready_for_simulation'])
            self.assertTrue(all(result['soil_profile'][key] is None for key in (
                'field_capacity_m3_m3', 'wilting_point_m3_m3', 'rooting_depth_m')))


if __name__ == '__main__':
    unittest.main()
