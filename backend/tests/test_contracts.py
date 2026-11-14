"""Contract and paired comparison failures that would mislead the frontend."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pydantic import ValidationError

from backend.app.api.schemas.contracts import (
    AnalogYear, CompareRequest, CompareResponse, Metrics,
    Quantiles, SimulationInput, SoilProfile,
)
from backend.app.intelligence.counterfactual import compare_runs
from scripts.export_contracts import (
    SCENARIOS, ZONE, export, make_fixture, make_mock_response, make_mock_runs,
)


class ContractTests(unittest.TestCase):
    def test_strong_el_nino_mock_matches_explicit_three_neighbor_decision(self):
        response = make_mock_response('strong_el_nino')
        self.assertEqual(len(response.analog_years), 3)
        self.assertTrue(all(rotation.metrics.modeled_water_deficit_mm.n == 3 for rotation in response.rotations))
        self.assertTrue(any('Only 3 analog years' in warning for warning in response.warnings))

    def test_full_season_fixture_roundtrip_and_explicit_unknowns(self):
        fixture = make_fixture()
        encoded = fixture.model_dump_json(by_alias=True)
        loaded = SimulationInput.model_validate_json(encoded)
        self.assertEqual(len(loaded.climate.days), 275)
        self.assertTrue(json.loads(encoded)['_mock'])
        self.assertIsNone(loaded.soil.field_capacity_m3_m3)
        self.assertIsNone(loaded.rotation.cycles[0].parameter_set_id)
        self.assertFalse(loaded.zona.validated)

    def test_missing_duplicate_or_out_of_order_days_rejected(self):
        for mutate in ('missing', 'duplicate', 'reordered'):
            with self.subTest(mutate=mutate):
                payload = make_fixture().model_dump(mode='json', by_alias=True)
                days = payload['climate']['days']
                if mutate == 'missing':
                    days.pop(2)
                elif mutate == 'duplicate':
                    days[2] = days[1]
                else:
                    days[1], days[2] = days[2], days[1]
                with self.assertRaises(ValidationError):
                    SimulationInput.model_validate(payload)

    def test_mock_cannot_be_relabelled_as_real_input(self):
        payload = make_fixture().model_dump(mode='json', by_alias=True)
        payload['_mock'] = False
        with self.assertRaises(ValidationError):
            SimulationInput.model_validate(payload)

    def test_unphysical_values_and_nonfinite_numbers_rejected(self):
        with self.assertRaises(ValidationError):
            SoilProfile(field_capacity_m3_m3=.1, wilting_point_m3_m3=.2,
                        rooting_depth_m=1, source_refs=[])
        for invalid in (-1, float('nan'), float('inf')):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                Metrics(crop_water_demand_mm=invalid, modeled_water_deficit_mm=0, water_stress_days=0)
        with self.assertRaises(ValidationError):
            AnalogYear(year=2026, distance=0)

    def test_request_requires_distinct_rotations_and_baseline(self):
        for rotations in (['rice_melon', 'rice_melon'], ['rice_legume', 'rice_sorghum']):
            with self.subTest(rotations=rotations), self.assertRaises(ValidationError):
                CompareRequest(zona=ZONE, scenario_id='neutral', rotation_ids=rotations)

    def test_quantile_order_and_empty_population_are_checked(self):
        with self.assertRaises(ValidationError):
            Quantiles(p10=3, p50=2, p90=1, n=5)
        with self.assertRaises(ValidationError):
            Quantiles(p10=1, p50=2, p90=3, n=0)

    def test_paired_delta_is_alternative_minus_baseline_for_each_year(self):
        response = make_mock_response()
        alt = response.rotations[1]
        self.assertEqual(alt.delta_vs_baseline.modeled_water_deficit_mm.p50, -10)
        self.assertEqual(alt.delta_vs_baseline.crop_water_demand_mm.p50, 20)
        self.assertEqual(alt.metrics.modeled_water_deficit_mm.n, 5)

    def test_quantiles_are_computed_after_pairing_not_subtracted_after_summary(self):
        analogs, runs = make_mock_runs()
        alternatives = iter([110, 40, 190, 100, 170])
        for run in runs:
            if run.rotation_id == 'rice_legume':
                run.metrics.modeled_water_deficit_mm = next(alternatives)
        response = compare_runs(CompareRequest(zona=ZONE, scenario_id='neutral'), analogs, runs)
        # Baseline values are 100,120,140,160,180; paired deltas 10,-80,50,-60,-10.
        alt = response.rotations[1]
        self.assertEqual(alt.delta_vs_baseline.modeled_water_deficit_mm.p50, -10)
        self.assertEqual(alt.metrics.modeled_water_deficit_mm.p50, 110)
        self.assertNotEqual(alt.delta_vs_baseline.modeled_water_deficit_mm.p50,
                            alt.metrics.modeled_water_deficit_mm.p50 -
                            response.rotations[0].metrics.modeled_water_deficit_mm.p50)

    def test_incomplete_metric_is_not_silently_dropped(self):
        analogs, runs = make_mock_runs()
        runs[1].metrics.modeled_water_deficit_mm = None
        result = compare_runs(CompareRequest(zona=ZONE, scenario_id='neutral'), analogs, runs)
        alt = result.rotations[1]
        self.assertIsNone(alt.metrics.modeled_water_deficit_mm.p50)
        self.assertEqual(alt.delta_vs_baseline.modeled_water_deficit_mm.n, 0)
        self.assertTrue(any('incomplete years' in warning for warning in result.warnings))

    def test_mixed_mock_real_missing_pair_and_changed_assumptions_rejected(self):
        for mutate in ('real', 'missing', 'duplicate', 'assumptions', 'environment'):
            with self.subTest(mutate=mutate):
                analogs, runs = make_mock_runs()
                if mutate == 'real':
                    runs[0].mock = False
                elif mutate == 'missing':
                    runs.pop()
                elif mutate == 'duplicate':
                    runs[-1] = runs[0]
                elif mutate == 'assumptions':
                    runs[1].assumptions = ['different management']
                else:
                    runs[1].environment_id = '0' * 64
                with self.assertRaises(ValueError):
                    compare_runs(CompareRequest(zona=ZONE, scenario_id='neutral'), analogs, runs)

    def test_comparator_revalidates_mutated_metrics_and_analog_years(self):
        for mutate in ('negative_metric', '2026_analog'):
            with self.subTest(mutate=mutate):
                analogs, runs = make_mock_runs()
                if mutate == 'negative_metric':
                    runs[0].metrics.crop_water_demand_mm = -1
                else:
                    previous = analogs[0].year
                    analogs[0].year = 2026
                    for run in runs:
                        if run.year == previous:
                            run.year = 2026
                with self.assertRaises(ValueError):
                    compare_runs(CompareRequest(zona=ZONE, scenario_id='neutral'), analogs, runs)

    def test_response_rejects_mock_and_scenario_mismatch_between_envelope_and_runs(self):
        for mismatch in ('_mock', 'scenario_id'):
            with self.subTest(mismatch=mismatch):
                payload = make_mock_response().model_dump(mode='json', by_alias=True)
                payload[mismatch] = False if mismatch == '_mock' else 'la_nina'
                with self.assertRaises(ValidationError):
                    CompareResponse.model_validate(payload)

    def test_export_is_reproducible_and_all_four_responses_validate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            export(root)
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*.json')}
            export(root)
            self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob('*.json')})
            for scenario in SCENARIOS:
                response = CompareResponse.model_validate_json(
                    (root / 'frontend/public/data' / f'compare-{scenario}.json').read_text(encoding='utf-8'))
                self.assertTrue(response.mock)
                self.assertEqual(response.scenario_id, scenario)
                self.assertEqual(len(response.rotations), 3)
                self.assertTrue(all(run.mock for rotation in response.rotations for run in rotation.runs))


if __name__ == '__main__':
    unittest.main()
