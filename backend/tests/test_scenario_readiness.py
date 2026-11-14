"""Coverage counts must never be presented as ET0 or KNN readiness."""

from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.app.infrastructure.power import PARAMETERS
from scripts.inspect_scenarios import inspect_scenarios, main


class ScenarioReadinessChecks(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.zone = {'id': 'test', 'latitude': 10.55, 'longitude': -85.5, 'validated': False}
        self.climate = {'_mock': True, 'zona': self.zone, 'source_refs': ['fixture:climate'],
                        'units': dict(PARAMETERS.values()), 'days': []}
        for year in (1981, 1982, 1983, 1984, 1985, 2026):
            for day in (1, 2, 3):
                self.climate['days'].append({'date': f'{year}-04-0{day}', 'precipitation_mm': 2.,
                    'tmin_c': 24., 'tmax_c': 35., 'relative_humidity_pct': 80.,
                    'solar_radiation_mj_m2_day': 20., 'wind_speed_2m_m_s': 2., 'et0_mm': None})
        self.oni = {'_mock': True, 'index': 'oni', 'source_refs': ['fixture:oni'],
                    'records': [{'year': year, 'season': 'ASO', 'anomaly_c': anomaly, 'index': 'oni'}
                                for year, anomaly in ((1981, 1.5), (1982, 2.), (1983, 1.6),
                                                      (1984, -.5), (1985, .5), (2026, 2.46))]}
        self.climate_path = self.write('climate.json', self.climate)
        self.oni_path = self.write('oni.json', self.oni)

    def write(self, name, value):
        path = self.directory / name
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def inspect(self, **kwargs):
        options = dict(start_mmdd='04-01', end_mmdd='04-03', oni_season='ASO',
                       as_of=date(2026, 11, 14), k=5, strong_el_nino_k=3)
        options.update(kwargs)
        return inspect_scenarios([self.climate_path], self.oni_path, **options)

    def test_override_and_oni_boundaries_are_explicit_without_running_knn(self):
        report = self.inspect()
        strong = report['scenarios']['strong_el_nino']
        self.assertEqual(strong['candidate_years_before_et0'], [1981, 1982, 1983])
        self.assertEqual(strong['requested_k'], 3)
        self.assertIsNone(strong['effective_k'])
        self.assertEqual(strong['status'], 'blocked_pending_reviewed_et0')
        self.assertEqual(report['scenarios']['neutral']['climate_oni_count_before_et0'], 0)
        self.assertEqual(report['scenarios']['la_nina']['candidate_years_before_et0'], [1984])
        self.assertEqual(report['scenarios']['like_2026']['climate_oni_count_before_et0'], 5)
        self.assertFalse(report['knn_has_run'])
        self.assertFalse(report['et0_reviewed'])

    def test_no_override_keeps_five_and_reports_insufficient_strong_years(self):
        report = self.inspect(strong_el_nino_k=None)
        strong = report['scenarios']['strong_el_nino']
        self.assertEqual(strong['requested_k'], 5)
        self.assertEqual(strong['status'], 'insufficient_climate_oni_years')

    def test_missing_solar_is_excluded_even_when_rain_tmax_are_present(self):
        self.climate['days'][0]['solar_radiation_mj_m2_day'] = None
        self.write('climate.json', self.climate)
        report = self.inspect()
        self.assertEqual(report['scenarios']['strong_el_nino']['climate_oni_count_before_et0'], 2)
        self.assertEqual(report['years'][0]['invalid_days_by_field']['solar_radiation_mj_m2_day'], 1)

    def test_future_period_and_missing_tracking_day_prevent_tracking(self):
        report = self.inspect(as_of=date(2026, 8, 31))
        self.assertEqual(report['scenarios']['like_2026']['status'], 'tracking_climate_oni_unavailable')
        self.climate['days'].pop()
        self.write('climate.json', self.climate)
        report = self.inspect()
        self.assertEqual(report['years'][-1]['missing_climate_dates'], ['2026-04-03'])
        self.assertEqual(report['scenarios']['like_2026']['status'], 'tracking_climate_oni_unavailable')

    def test_shared_loader_rejects_conflicts_mixed_zone_and_wrong_units(self):
        for change in ('zone', 'units', 'conflict'):
            other = json.loads(json.dumps(self.climate))
            if change == 'zone':
                other['zona']['latitude'] = 11
            elif change == 'units':
                other['units']['solar_radiation_mj_m2_day'] = 'kWh/m2/day'
            else:
                other['days'][0]['precipitation_mm'] = 99
            path = self.write('other.json', other)
            with self.subTest(change=change), self.assertRaises(ValueError):
                inspect_scenarios([self.climate_path, path], self.oni_path, start_mmdd='04-01',
                    end_mmdd='04-03', oni_season='ASO', as_of=date(2026, 11, 14), k=5)

    def test_cli_defaults_to_three_only_for_strong_el_nino(self):
        output = self.directory / 'readiness.json'
        result = main(['--climate', str(self.climate_path), '--oni', str(self.oni_path),
            '--start-mmdd', '04-01', '--end-mmdd', '04-03', '--oni-season', 'ASO',
            '--as-of', '2026-11-14', '--output', str(output)])
        self.assertEqual(result, 0)
        report = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(report['k_by_scenario'], {'strong_el_nino': 3, 'neutral': 5, 'la_nina': 5, 'like_2026': 5})
        self.assertFalse(report['knn_has_run'])


if __name__ == '__main__':
    unittest.main()
