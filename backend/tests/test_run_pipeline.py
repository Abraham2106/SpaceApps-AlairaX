"""Analog document → three rotations → paired comparison integration."""

import unittest

from backend.app.api.schemas.contracts import CompareResponse
from scripts.export_contracts import ZONE, make_fixture
from scripts.run_comparison import compare_from_analogs


class RunPipelineTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            '_mock': True, 'zona': ZONE.model_dump(mode='json'),
            'source_refs': ['test-analog-selection'], 'warnings': ['analog envelope warning'],
            'scenarios': {
                'neutral': {
                    '_mock': True, 'status': 'available', 'k': 2,
                    'neighbors': [{'year': 2000, 'distance': .1}, {'year': 2001, 'distance': .2}],
                    'warnings': ['scenario warning'],
                },
            },
        }
        self.inputs = []
        for year in (2000, 2001):
            for rotation_id, crop_id in [('rice_melon', 'melon'), ('rice_legume', 'legume'),
                                         ('rice_sorghum', 'sorghum')]:
                simulation = make_fixture()
                simulation.climate.year = year
                simulation.climate.start = simulation.climate.start.replace(year=year)
                simulation.climate.end = simulation.climate.end.replace(year=year)
                for day in simulation.climate.days:
                    day.date = day.date.replace(year=year)
                simulation.rotation.rotation_id = rotation_id
                simulation.rotation.cycles[1].crop_id = crop_id
                for cycle in simulation.rotation.cycles:
                    cycle.sowing_date = cycle.sowing_date.replace(year=year)
                    cycle.harvest_date = cycle.harvest_date.replace(year=year)
                simulation.warnings = ['input climate warning']
                self.inputs.append(simulation)

    def test_three_rotations_per_analog_and_provenance_survive_export(self):
        called = []

        def synthetic_kernel(**kwargs):
            called.append((kwargs['climate'].year, kwargs['rotation'].rotation_id))
            return {
                'metrics': {'crop_water_demand_mm': 100, 'modeled_water_deficit_mm': 20,
                            'water_stress_days': 1},
                'daily_balance': [], 'assumptions': ['synthetic integration fixture'],
                'source_refs': ['test-kernel-fixture'], 'warnings': ['kernel warning'],
                'model_version': 'synthetic-integration-v1',
            }

        result = compare_from_analogs(self.document, 'neutral', self.inputs,
                                      simulate_rotation=synthetic_kernel)
        self.assertEqual(set(called), {(year, rotation) for year in (2000, 2001)
                                      for rotation in ('rice_melon', 'rice_legume', 'rice_sorghum')})
        self.assertEqual(len(called), 6)
        self.assertTrue(result.mock)
        self.assertEqual(len(result.rotations), 3)
        self.assertTrue(all(len(rotation.runs) == 2 for rotation in result.rotations))
        for year in (2000, 2001):
            hashes = {run.environment_id for rotation in result.rotations for run in rotation.runs
                      if run.year == year}
            self.assertEqual(len(hashes), 1)
        self.assertEqual(set(result.source_refs), {
            'synthetic-fixture-v1', 'test-kernel-fixture', 'test-analog-selection',
        })
        self.assertTrue({'input climate warning', 'kernel warning',
                         'analog envelope warning', 'scenario warning'}.issubset(result.warnings))
        loaded = CompareResponse.model_validate_json(result.model_dump_json(by_alias=True))
        self.assertEqual(loaded.scenario_id, 'neutral')
        self.assertEqual([a.year for a in loaded.analog_years], [2000, 2001])

    def test_input_mock_mismatch_rejected_before_callback(self):
        self.inputs[0].mock = False

        def must_not_run(**kwargs):
            self.fail('kernel called before analog/input mock status check')

        with self.assertRaisesRegex(ValueError, 'share mock status'):
            compare_from_analogs(self.document, 'neutral', self.inputs, simulate_rotation=must_not_run)

    def test_analog_envelope_scenario_mock_mismatch_rejected_before_callback(self):
        self.document['scenarios']['neutral']['_mock'] = False

        def must_not_run(**kwargs):
            self.fail('kernel called before analog envelope validation')

        with self.assertRaisesRegex(ValueError, 'mock flags must agree'):
            compare_from_analogs(self.document, 'neutral', self.inputs, simulate_rotation=must_not_run)

    def test_unavailable_analog_scenario_never_runs_kernel(self):
        self.document['scenarios']['neutral'] = {'status': 'unavailable', 'reason': 'reviewed ET0 missing'}

        def must_not_run(**kwargs):
            self.fail('kernel called for an unavailable scenario')

        with self.assertRaisesRegex(ValueError, 'unavailable: reviewed ET0 missing'):
            compare_from_analogs(self.document, 'neutral', self.inputs, simulate_rotation=must_not_run)


if __name__ == '__main__':
    unittest.main()
