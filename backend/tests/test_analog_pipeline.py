"""Integration through normalized files, reviewed ET0 and CLI exports."""

from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.app.intelligence.analog_pipeline import build_pipeline
from scripts.build_analogs import main


ZONE = {'id': 'test', 'name': 'Synthetic point', 'latitude': 10.55,
        'longitude': -85.5, 'validated': False}


class AnalogPipelineChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.climate = {
            '_mock': True, 'zona': ZONE, 'source_refs': ['fixture:climate'],
            'units': {'precipitation_mm': 'mm/day', 'tmax_c': 'C'},
            'days': [{'date': f'{year}-04-0{day}', 'precipitation_mm': float(day),
                      'tmax_c': 35., 'et0_mm': None}
                     for year in (1981, 1982, 1983, 2026) for day in (1, 2, 3)],
        }
        self.oni = {'_mock': True, 'index': 'oni', 'source_refs': ['fixture:oni'],
                    'records': [{'year': year, 'season': 'AMJ', 'anomaly_c': value,
                                 'index': 'oni'}
                                for year, value in ((1981, 2), (1982, 0), (1983, -1), (2026, 1))]}
        self.et0 = {'_mock': True, 'zona': ZONE, 'source_refs': ['fixture:et0'],
                    'reviewed': True, 'reviewed_by': 'Synthetic fixture, not field validation',
                    'model_version': 'fixture-only', 'units': 'mm/day',
                    'values': {row['date']: 4.0 for row in self.climate['days']}}
        self.paths = [self.write(name, data) for name, data in
                      (('climate.json', self.climate), ('oni.json', self.oni), ('et0.json', self.et0))]

    def write(self, name, data):
        path = self.directory / name
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def build(self, **kwargs):
        options = dict(et0_file=self.paths[2], start_mmdd='04-01', end_mmdd='04-03',
                       oni_season='AMJ', as_of=date(2026, 11, 14), k=1)
        options.update(kwargs)
        return build_pipeline([self.paths[0]], self.paths[1], **options)

    def test_cli_exports_four_scenarios_and_provenance(self):
        result = main(['--climate', str(self.paths[0]), '--oni', str(self.paths[1]),
                       '--et0', str(self.paths[2]), '--start-mmdd', '04-01',
                       '--end-mmdd', '04-03', '--oni-season', 'AMJ', '--as-of',
                       '2026-11-14', '--k', '1', '--strong-el-nino-k', '1', '--output-dir', str(self.directory / 'output')])
        self.assertEqual(result, 0)
        output = json.loads((self.directory / 'output/analogos.json').read_text(encoding='utf-8'))
        features = json.loads((self.directory / 'output/features.json').read_text(encoding='utf-8'))
        self.assertEqual(len(features['features']), 4)
        self.assertTrue(output['_mock'])
        self.assertEqual(len(output['provenance']), 3)
        for scenario in output['scenarios'].values():
            self.assertEqual(scenario['status'], 'available')
            self.assertNotIn(2026, scenario['candidate_years'])
            self.assertTrue(scenario['k_sensitivity'])

    def test_missing_reviewed_et0_exports_unavailable_without_fake_features(self):
        features, analogs = self.build(et0_file=None)
        self.assertEqual(features['features'], [])
        self.assertEqual(len(features['excluded_years']), 4)
        self.assertTrue(all(value['status'] == 'unavailable' for value in analogs['scenarios'].values()))

    def test_no_silent_reduction_of_k(self):
        _, analogs = self.build(k=5)
        self.assertTrue(all(value['status'] == 'unavailable' and value['k'] == 5
                            for value in analogs['scenarios'].values()))

    def test_explicit_strong_el_nino_override_keeps_other_scenarios_at_five(self):
        historical_years = list(range(1981, 1994))
        self.climate['days'] = [{'date': f'{year}-04-0{day}', 'precipitation_mm': 2.,
                                 'tmax_c': 35., 'et0_mm': None}
                                for year in historical_years + [2026] for day in (1, 2, 3)]
        self.oni['records'] = [{'year': year, 'season': 'AMJ', 'anomaly_c': 2. if i < 3 else 0. if i < 8 else -1.,
                                'index': 'oni'} for i, year in enumerate(historical_years)]
        self.oni['records'].append({'year': 2026, 'season': 'AMJ', 'anomaly_c': 1., 'index': 'oni'})
        self.et0['values'] = {row['date']: 4. for row in self.climate['days']}
        self.write('climate.json', self.climate)
        self.write('oni.json', self.oni)
        self.write('et0.json', self.et0)
        _, analogs = self.build(k=5, strong_el_nino_k=3)
        self.assertEqual(analogs['k_by_scenario'], {'strong_el_nino': 3, 'neutral': 5, 'la_nina': 5, 'like_2026': 5})
        for name, result in analogs['scenarios'].items():
            self.assertEqual(result['status'], 'available')
            self.assertEqual(result['effective_k'], 3 if name == 'strong_el_nino' else 5)
            self.assertEqual(len(result['neighbors']), result['requested_k'])
        self.assertTrue(any('Small analog sample' in warning for warning in analogs['scenarios']['strong_el_nino']['warnings']))

    def test_missing_daily_et0_excludes_only_affected_year(self):
        self.et0['values']['1981-04-02'] = None
        self.write('et0.json', self.et0)
        features, _ = self.build()
        self.assertEqual([row['year'] for row in features['excluded_years']], [1981])
        self.assertNotIn(1981, [row['year'] for row in features['features']])

    def test_tracking_and_oni_must_end_before_information_cutoff(self):
        features, analogs = self.build(as_of=date(2026, 4, 3))
        self.assertIn('ONI period extends', features['excluded_years'][0]['reason'])
        self.assertEqual(analogs['scenarios']['like_2026']['status'], 'unavailable')
        features, _ = self.build(end_mmdd='12-31')
        self.assertTrue(any(row['year'] == 2026 and 'beyond as_of' in row['reason']
                            for row in features['excluded_years']))

    def test_compatible_overlap_deduplicates_but_conflict_rejects(self):
        second = self.write('overlap.json', self.climate)
        options = dict(et0_file=self.paths[2], start_mmdd='04-01', end_mmdd='04-03',
                       oni_season='AMJ', as_of=date(2026, 11, 14), k=1)
        features, _ = build_pipeline([self.paths[0], second], self.paths[1], **options)
        self.assertEqual(len(features['features']), 4)
        self.climate['days'][0]['precipitation_mm'] = 99
        self.write('overlap.json', self.climate)
        with self.assertRaisesRegex(ValueError, 'conflicting overlapping'):
            build_pipeline([self.paths[0], second], self.paths[1], **options)

    def test_unreviewed_et0_zone_and_mock_mismatch_rejected(self):
        for key, value in (('reviewed', False), ('_mock', False), ('zona', ZONE | {'latitude': 11})):
            with self.subTest(key=key):
                original = self.et0[key]
                self.et0[key] = value
                self.write('et0.json', self.et0)
                with self.assertRaises(ValueError):
                    self.build()
                self.et0[key] = original

    def test_inline_et0_cannot_bypass_review_and_roni_cannot_replace_oni(self):
        self.climate['days'][0]['et0_mm'] = 4
        self.write('climate.json', self.climate)
        with self.assertRaisesRegex(ValueError, 'reviewed ET0 file'):
            self.build()
        self.climate['days'][0]['et0_mm'] = None
        self.write('climate.json', self.climate)
        self.oni['index'] = 'roni'
        self.write('oni.json', self.oni)
        with self.assertRaisesRegex(ValueError, 'not RONI'):
            self.build()


if __name__ == '__main__':
    unittest.main()
