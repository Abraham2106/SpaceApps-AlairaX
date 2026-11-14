"""Exercise the actual numerical kernel while retaining synthetic input labels."""

import json
from pathlib import Path
import unittest

from backend.app.application.prepare_inputs import ReviewedET0
from scripts.inspect_calendars import inspect_calendars
from scripts.smoke_kernel import run_smoke


class KernelHandoffTests(unittest.TestCase):
    def test_real_kernel_cross_year_batch_remains_mock(self):
        result = run_smoke()
        self.assertTrue(result.mock)
        self.assertEqual(len(result.rotations), 3)
        for rotation in result.rotations:
            self.assertEqual(len(rotation.runs), 2)
            for run in rotation.runs:
                self.assertTrue(run.mock)
                self.assertEqual(run.model_version, 'fao56-kernel-0.1.0')
                self.assertIn(len(run.daily_balance), (365, 366))
                self.assertIsNotNone(run.metrics.modeled_water_deficit_mm)
        self.assertTrue(any('KNN was not run' in warning for warning in result.warnings))

    def test_actual_et0_metadata_does_not_imply_review(self):
        path = Path('datasets/processed/et0/et0_10.55_-85.5.json')
        payload = json.loads(path.read_text(encoding='utf-8'))
        model = ReviewedET0.model_validate(payload)
        self.assertFalse(model.reviewed)
        self.assertIsNone(model.reviewed_by)
        self.assertEqual(len(model.values), 16754)
        payload['reviewed'] = True
        with self.assertRaisesRegex(ValueError, 'named reviewer'):
            ReviewedET0.model_validate(payload)

    def test_calendar_audit_preserves_and_identifies_overlaps(self):
        report = inspect_calendars(2015)
        by_rotation = {r['rotation_id']: r for r in report['rotations']}
        self.assertFalse(report['simulation_run'])
        self.assertEqual(by_rotation['rice_melon']['conflicts'], [])
        self.assertTrue(any(c['type'] == 'overlap' for c in by_rotation['rice_legume']['conflicts']))
        self.assertTrue(any(c['type'] == 'overlap' for c in by_rotation['rice_sorghum']['conflicts']))
        self.assertEqual(by_rotation['rice_melon']['cycles'][1]['harvest'], '2016-03-29')
