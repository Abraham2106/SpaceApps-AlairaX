"""Units actually returned by SoilGrids Swagger on 14 November 2026."""

import unittest

from backend.app.infrastructure.soil import normalize_soil


class LiveUnitTests(unittest.TestCase):
    def test_api_scaled_volume_percent_converts_to_volume_fraction(self):
        payload = {'properties': {'layers': [
            {'name': name, 'unit_measure': {'mapped_units': '(10-2 cm³/cm³)*10',
                'd_factor': 10, 'target_units': '10-2 cm³/cm³'},
             'depths': [{'label': '0-5cm', 'values': {'mean': value}}]}
            for name, value in [('wv0033', 333), ('wv1500', 200)]
        ]}}
        rows = normalize_soil(payload, ('wv0033', 'wv1500'), ('0-5cm',))
        self.assertAlmostEqual(rows[0]['value'], .333)
        self.assertAlmostEqual(rows[1]['value'], .200)
        self.assertTrue(all(row['unit'] == 'm3/m3' and row['reason'] is None for row in rows))
