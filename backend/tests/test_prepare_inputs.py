"""Reviewed artifacts must produce paired, reproducible kernel inputs."""

from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from backend.app.application.compare import environment_fingerprint
from backend.app.application.prepare_inputs import ComparisonSetup, prepare_inputs
from scripts.export_contracts import make_fixture
from scripts.run_comparison import compare_from_analogs


class PrepareInputTests(unittest.TestCase):
    def setUp(self):
        fixture = make_fixture()
        self.zone = fixture.zona.model_dump(mode='json')
        self.analogs = {
            '_mock': True, 'zona': self.zone, 'source_refs': ['synthetic-selection'], 'warnings': [],
            'scenarios': {'neutral': {'status': 'available', '_mock': True, 'k': 1,
                                      'neighbors': [{'year': 2015, 'distance': .1}]}}}
        rotations = []
        for rid, crop in [('rice_melon', 'melon'), ('rice_legume', 'legume'), ('rice_sorghum', 'sorghum')]:
            rotation = fixture.rotation.model_copy(deep=True)
            rotation.rotation_id = rid
            rotation.cycles[1].crop_id = crop
            rotations.append(rotation)
        self.setup = ComparisonSetup(mock=True, generado=fixture.generado, zona=fixture.zona,
            source_refs=['synthetic-setup'], warnings=['synthetic fixture'], reviewed_by='test-only',
            soil=fixture.soil, rotations_by_year={2015: rotations},
            assumptions_by_year={2015: fixture.assumptions})
        self.climate = {'_mock': True, 'zona': self.zone, 'source_refs': ['synthetic-climate'],
            'warnings': [], 'units': {'precipitation_mm': 'mm/day', 'tmin_c': 'C', 'tmax_c': 'C',
                'relative_humidity_pct': '%', 'wind_speed_2m_m_s': 'm/s',
                'solar_radiation_mj_m2_day': 'MJ/m^2/day'},
            'days': [d.model_dump(mode='json') for d in fixture.climate.days]}
        self.et0 = {'_mock': True, 'zona': self.zone, 'reviewed': True, 'reviewed_by': 'test-only',
                    'model_version': 'synthetic-fixture', 'units': 'mm/day',
                    'source_refs': ['synthetic-et0'],
                    'values': {row['date']: 4.0 for row in self.climate['days']}}

    def run_prepare(self, climates=None):
        return prepare_inputs(self.analogs, 'neutral', climates or [self.climate], self.et0,
                              self.setup, start_mmdd='04-01', end_mmdd='12-31')

    def test_three_inputs_with_equal_environment_and_independent_climate(self):
        inputs = self.run_prepare()
        self.assertEqual(len(inputs), 3)
        self.assertEqual(len({environment_fingerprint(i) for i in inputs}), 1)
        self.assertEqual(len(inputs[0].climate.days), 275)
        self.assertTrue(all(i.mock for i in inputs))
        self.assertEqual(inputs[0].climate.days[0].et0_mm, 4)
        self.assertIn('synthetic-et0', inputs[0].source_refs)
        inputs[0].climate.days[0].precipitation_mm = 999
        self.assertNotEqual(inputs[0].climate.days[0], inputs[1].climate.days[0])

    def test_identical_overlaps_deduplicated_conflicts_rejected(self):
        self.assertEqual(len(self.run_prepare([self.climate, deepcopy(self.climate)])), 3)
        conflict = deepcopy(self.climate)
        conflict['days'][0]['precipitation_mm'] += 1
        with self.assertRaisesRegex(ValueError, 'conflicting climate'):
            self.run_prepare([self.climate, conflict])

    def test_unavailable_scenario_rejected(self):
        self.analogs['scenarios']['neutral'] = {'status': 'unavailable', 'reason': 'ET0 missing'}
        with self.assertRaisesRegex(ValueError, 'unavailable: ET0 missing'):
            self.run_prepare()

    def test_no_calendar_or_management_is_invented(self):
        self.setup.rotations_by_year = {}
        with self.assertRaisesRegex(ValueError, 'calendars and management'):
            self.run_prepare()

    def test_no_missing_date_imputation(self):
        self.climate['days'].pop()
        with self.assertRaisesRegex(ValueError, 'missing climate date'):
            self.run_prepare()

    def test_review_zone_mock_and_unit_guardrails(self):
        for key, value, message in [('reviewed', False, 'reviewed'), ('units', 'kWh', 'units'),
                                    ('_mock', False, 'mock'), ('zona', {}, 'zone')]:
            with self.subTest(key=key):
                previous = self.et0[key]
                self.et0[key] = value
                with self.assertRaisesRegex(ValueError, message):
                    self.run_prepare()
                self.et0[key] = previous

    def test_canonical_climate_units_required(self):
        self.climate['units']['solar_radiation_mj_m2_day'] = 'kWh/m^2/day'
        with self.assertRaisesRegex(ValueError, 'normalized contract units'):
            self.run_prepare()

    def test_three_distinct_rotations_and_historical_years(self):
        self.setup.rotations_by_year[2015].pop()
        with self.assertRaisesRegex(ValueError, 'three distinct rotation'):
            self.run_prepare()

    def test_inline_et0_cannot_bypass_reviewed_artifact(self):
        self.climate['days'][0]['et0_mm'] = 10
        with self.assertRaisesRegex(ValueError, 'reviewed ET0 artifact'):
            self.run_prepare()

    def test_real_incomplete_et0_rejected(self):
        self.setup.mock = False
        self.setup.zona.validated = True
        zone = self.setup.zona.model_dump(mode='json')
        self.setup.soil.field_capacity_m3_m3 = .3
        self.setup.soil.wilting_point_m3_m3 = .1
        self.setup.soil.rooting_depth_m = .5
        self.setup.assumptions_by_year[2015].irrigation_mode = 'rainfed'
        self.setup.assumptions_by_year[2015].initial_soil_water_fraction = .5
        for rotation in self.setup.rotations_by_year[2015]:
            rotation.calendar_status = 'confirmed'
            for cycle in rotation.cycles:
                cycle.parameter_set_id = 'test-parameter-id'
        for document in (self.et0, self.climate, self.analogs):
            document['_mock'], document['zona'] = False, zone
        self.analogs['scenarios']['neutral']['_mock'] = False
        self.et0['values']['2015-04-01'] = None
        with self.assertRaisesRegex(ValueError, 'incomplete real climate or ET0'):
            self.run_prepare()

    def test_empty_boolean_string_or_out_of_range_k_rejected(self):
        for k in (0, True, '1', 46):
            with self.subTest(k=k):
                self.analogs['scenarios']['neutral']['k'] = k
                self.analogs['scenarios']['neutral']['neighbors'] = [] if k == 0 else [{'year': 2015, 'distance': .1}]
                with self.assertRaisesRegex(ValueError, 'integer from 1 to 45'):
                    self.run_prepare()

    def test_et0_flags_require_literal_booleans(self):
        for key, value in [('_mock', 'true'), ('_mock', 1), ('reviewed', 'true'), ('reviewed', 1)]:
            with self.subTest(key=key, value=value):
                previous = self.et0[key]
                self.et0[key] = value
                with self.assertRaises(ValueError):
                    self.run_prepare()
                self.et0[key] = previous

    def test_prepared_zones_and_management_are_independent(self):
        inputs = self.run_prepare()
        inputs[0].zona.name = 'changed'
        inputs[0].assumptions.notes.append('changed')
        inputs[0].soil.source_refs.append('changed')
        inputs[0].rotation.cycles[0].parameter_set_id = 'changed'
        self.assertNotEqual(inputs[1].zona.name, 'changed')
        self.assertNotIn('changed', inputs[1].assumptions.notes)
        self.assertNotIn('changed', inputs[1].soil.source_refs)
        self.assertIsNone(inputs[1].rotation.cycles[0].parameter_set_id)

    def test_setup_can_validate_original_zone_without_rewriting_sources_and_run_comparison(self):
        self.setup.mock = False
        self.setup.zona.validated = True
        self.setup.soil.field_capacity_m3_m3 = .3
        self.setup.soil.wilting_point_m3_m3 = .1
        self.setup.soil.rooting_depth_m = .5
        self.setup.assumptions_by_year[2015].irrigation_mode = 'rainfed'
        self.setup.assumptions_by_year[2015].initial_soil_water_fraction = .5
        for rotation in self.setup.rotations_by_year[2015]:
            rotation.calendar_status = 'confirmed'
            for cycle in rotation.cycles:
                cycle.parameter_set_id = 'synthetic-test-parameter'
        for document in (self.et0, self.climate, self.analogs):
            document['_mock'] = False
        self.analogs['scenarios']['neutral']['_mock'] = False
        original_sources = deepcopy((self.et0, self.climate, self.analogs))
        inputs = self.run_prepare()
        self.assertTrue(all(simulation.zona.validated for simulation in inputs))
        self.assertEqual(original_sources, (self.et0, self.climate, self.analogs))

        def synthetic_kernel(**kwargs):
            return dict(
                metrics=dict(crop_water_demand_mm=100, modeled_water_deficit_mm=20, water_stress_days=0),
                daily_balance=[dict(date=day.date, crop_water_demand_mm=None,
                                    modeled_water_deficit_mm=None, soil_water_storage_mm=None,
                                    water_stress=None) for day in kwargs['climate'].days],
                assumptions=['synthetic integration test'], source_refs=['synthetic-kernel-fixture'],
                warnings=[], model_version='synthetic-test-only',
            )

        response = compare_from_analogs(self.analogs, 'neutral', inputs, simulate_rotation=synthetic_kernel)
        self.assertTrue(response.zona.validated)
        self.assertEqual(len(response.rotations), 3)

    def test_zone_identity_cannot_change_coordinates(self):
        self.et0['zona'] = dict(self.et0['zona'], latitude=10.56)
        with self.assertRaisesRegex(ValueError, 'same zone'):
            self.run_prepare()

    def write_cli_artifacts(self, base, *, setup_name='setup.json'):
        payloads = {'analogs.json': self.analogs, 'et0.json': self.et0, 'climate.json': self.climate,
                    setup_name: self.setup.model_dump(mode='json', by_alias=True)}
        for name, payload in payloads.items():
            (base / name).write_text(json.dumps(payload), encoding='utf-8')
        return [sys.executable, '-m', 'scripts.prepare_comparison', '--analogs', str(base / 'analogs.json'),
                '--scenario', 'neutral', '--climate', str(base / 'climate.json'), '--et0', str(base / 'et0.json'),
                '--setup', str(base / setup_name), '--start-mmdd', '04-01', '--end-mmdd', '12-31']

    def test_cli_prevents_output_manifest_or_temporary_overwriting_inputs(self):
        for setup_name in ('batch.json', 'batch.manifest.json', 'batch.json.tmp', 'batch.manifest.json.tmp'):
            with self.subTest(setup_name=setup_name), TemporaryDirectory() as directory:
                base = Path(directory)
                command = self.write_cli_artifacts(base, setup_name=setup_name)
                before = {path.name: path.read_bytes() for path in base.iterdir()}
                result = subprocess.run(command + ['--output', str(base / 'batch.json'), '--allow-mock'],
                                        capture_output=True, text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('must not overwrite input artifacts', result.stderr)
                self.assertEqual(before, {path.name: path.read_bytes() for path in base.iterdir()})

    def test_cli_writes_array_and_provenance_manifest_without_changing_inputs(self):
        with TemporaryDirectory() as directory:
            base = Path(directory)
            command = self.write_cli_artifacts(base)
            before = {path.name: path.read_bytes() for path in base.iterdir()}
            output = base / 'batch.json'
            result = subprocess.run(command + ['--output', str(output), '--allow-mock'], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(json.loads(output.read_text(encoding='utf-8'))), 3)
            manifest = json.loads((base / 'batch.manifest.json').read_text(encoding='utf-8'))
            self.assertTrue(manifest['_mock'])
            self.assertEqual(manifest['input_count'], 3)
            self.assertEqual(manifest['output_sha256'], sha256(output.read_bytes()).hexdigest())
            self.assertEqual(len(manifest['artifacts']), 4)
            self.assertTrue(all((base / name).read_bytes() == body for name, body in before.items()))

    def test_cli_rejects_synthetic_setup_without_explicit_flag(self):
        with TemporaryDirectory() as directory:
            base = Path(directory)
            command = self.write_cli_artifacts(base)
            output = base / 'batch.json'
            result = subprocess.run(command + ['--output', str(output)], capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('requires --allow-mock', result.stderr)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
