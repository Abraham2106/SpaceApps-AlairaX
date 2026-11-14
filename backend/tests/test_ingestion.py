"""Scientific ingestion regressions: no hidden zeros, units, vintages or clipping."""

from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from backend.app.infrastructure.cache import RawCache
from backend.app.infrastructure.noaa import parse_enso
from backend.app.infrastructure.power import PARAMETERS, normalize_power, power_url


def example_payload():
    values = {'PRECTOTCORR': [5, 523], 'T2M_MIN': [21, 22], 'T2M_MAX': [31, 32],
              'RH2M': [70, 75], 'WS2M': [2, 3], 'ALLSKY_SFC_SW_DWN': [20, 21]}
    return {'header': {'fill_value': -999},
            'parameters': {p: {'units': unit} for p, (_, unit) in PARAMETERS.items()},
            'properties': {'parameter': {p: dict(zip(('20240101', '20240102'), vals)) for p, vals in values.items()}}}


class PowerTests(unittest.TestCase):
    def test_calendar_gaps_remain_null_not_dry_days(self):
        payload = example_payload()
        payload['properties']['parameter']['PRECTOTCORR']['20240101'] = -999
        result = normalize_power(payload, date(2024, 1, 1), date(2024, 1, 3))
        self.assertEqual(len(result['days']), 3)
        self.assertIsNone(result['days'][0]['precipitation_mm'])
        self.assertIsNone(result['days'][2]['precipitation_mm'])
        self.assertTrue(all(row['et0_mm'] is None for row in result['days']))

    def test_rain_extremes_flagged_and_not_clipped_or_calibrated(self):
        result = normalize_power(example_payload(), date(2024, 1, 1), date(2024, 1, 2))
        self.assertEqual(result['days'][1]['precipitation_mm'], 523)
        self.assertEqual(result['quality_control']['issues'][0]['reason'], 'high_rainfall_review_required')
        self.assertIsNone(result['quality_control']['bias_correction'])

    def test_radiation_units_are_not_guessed(self):
        payload = example_payload()
        first = normalize_power(payload, date(2024, 1, 1), date(2024, 1, 1))
        self.assertEqual(first['days'][0]['solar_radiation_mj_m2_day'], 20)
        payload['parameters']['ALLSKY_SFC_SW_DWN']['units'] = 'kW-hr/m^2/day'
        converted = normalize_power(payload, date(2024, 1, 1), date(2024, 1, 1))
        self.assertEqual(converted['days'][0]['solar_radiation_mj_m2_day'], 72)
        payload['parameters']['ALLSKY_SFC_SW_DWN']['units'] = 'W/m^2'
        with self.assertRaises(ValueError):
            normalize_power(payload, date(2024, 1, 1), date(2024, 1, 1))

    def test_invalid_ranges_and_inverted_temperatures_become_null(self):
        payload = example_payload()
        payload['properties']['parameter']['RH2M']['20240101'] = 102
        payload['properties']['parameter']['WS2M']['20240101'] = -2
        payload['properties']['parameter']['T2M_MIN']['20240101'] = 40
        result = normalize_power(payload, date(2024, 1, 1), date(2024, 1, 1))
        row = result['days'][0]
        for field in ('relative_humidity_pct', 'wind_speed_2m_m_s', 'tmin_c', 'tmax_c'):
            self.assertIsNone(row[field])

    def test_historical_missing_variable_is_null_with_qc(self):
        payload = example_payload()
        del payload['properties']['parameter']['WS2M']
        del payload['parameters']['WS2M']
        result = normalize_power(payload, date(2024, 1, 1), date(2024, 1, 1))
        self.assertIsNone(result['days'][0]['wind_speed_2m_m_s'])
        self.assertIsNone(result['provider_units']['WS2M'])
        self.assertEqual(result['quality_control']['issues'][0]['reason'], 'missing')

    def test_url_explicit_units_and_time_standard(self):
        url = power_url(10.55, -85.5, date(2024, 1, 1), date(2024, 1, 5))
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query['units'], ['metric'])
        self.assertEqual(query['time-standard'], ['LST'])
        self.assertEqual(query['community'], ['AG'])
        with self.assertRaises(ValueError):
            power_url(float('nan'), -85.5, date(2024, 1, 1), date(2024, 1, 5))


class NoaaTests(unittest.TestCase):
    def test_oni_reads_anomaly_not_total_and_preserves_season(self):
        result = parse_enso('SEAS YR TOTAL ANOM\nAMJ 2024 28.0 0.7\nOND 2024 26.0 -0.3\n', 'oni')
        self.assertEqual(result[0]['anomaly_c'], .7)
        self.assertEqual(result[0]['fase_temporada'], 'AMJ')
        self.assertEqual(result[0]['center_month'], 5)

    def test_roni_header_and_missing_sentinel(self):
        result = parse_enso('SEAS YR ANOM\nDJF 2024 -999\nAMJ 2024 0.5\n', 'roni')
        self.assertIsNone(result[0]['anomaly_c'])
        self.assertIsNone(result[0]['fase_temporada'])
        self.assertEqual(result[1]['index'], 'roni')

    def test_duplicate_or_malformed_noaa_is_rejected(self):
        for content in ('SEAS YR ANOM\nAMJ 2024 0.5\nAMJ 2024 .7',
                        'SEAS YR ANOM\nAMJ 2024', '<html>Error</html>'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                parse_enso(content, 'roni')


class FakeResponse:
    status = 200
    headers = {'Content-Type': 'application/json', 'ETag': 'test'}

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self.body


class CacheTests(unittest.TestCase):
    def test_refresh_preserves_original_snapshots_and_offline_replays(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = RawCache(folder)
            with patch('backend.app.infrastructure.cache.urlopen', return_value=FakeResponse(b'{"value":1}')) as fetch:
                original, metadata = cache.get('https://example.test/climate')
                cached, cached_metadata = cache.get('https://example.test/climate', offline=True)
                self.assertEqual(fetch.call_count, 1)
                self.assertEqual((original, metadata), (cached, cached_metadata))
            with patch('backend.app.infrastructure.cache.urlopen', return_value=FakeResponse(b'{"value":2}')):
                cache.get('https://example.test/climate', refresh=True)
            self.assertEqual(len(list(Path(folder).glob('*.body'))), 2)
            self.assertEqual(len(list(Path(folder).glob('*.snapshot.json'))), 2)

    def test_corrupt_cache_fails_instead_of_silently_used(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = RawCache(folder)
            with patch('backend.app.infrastructure.cache.urlopen', return_value=FakeResponse(b'original')):
                _, metadata = cache.get('https://example.test/climate')
            (Path(folder) / f'{metadata["sha256"]}.body').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                cache.get('https://example.test/climate', offline=True)

    def test_offline_cache_miss_never_fetches(self):
        with tempfile.TemporaryDirectory() as folder, patch('backend.app.infrastructure.cache.urlopen') as fetch:
            with self.assertRaises(FileNotFoundError):
                RawCache(folder).get('https://example.test/missing', offline=True)
            fetch.assert_not_called()

    def test_explicit_refresh_repairs_corruption_even_if_remote_body_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = RawCache(folder)
            url = 'https://example.test/climate'
            with patch('backend.app.infrastructure.cache.urlopen', return_value=FakeResponse(b'original')):
                _, metadata = cache.get(url)
                (Path(folder) / f'{metadata["sha256"]}.body').write_bytes(b'corrupt')
                repaired, _ = cache.get(url, refresh=True)
            replay, _ = cache.get(url, offline=True)
            self.assertEqual(repaired, b'original')
            self.assertEqual(replay, repaired)


if __name__ == '__main__':
    unittest.main()
