"""Guardrails for paired comparisons, independent of kernel equations."""

from datetime import date, datetime, timezone
import unittest

from backend.app.api.schemas.contracts import (
    AnalogYear, ClimateDay, ClimateSeason, CompareRequest, CropCycle,
    ModelAssumptions, RotationSchedule, SimulationInput, SoilProfile, Zone,
)
from backend.app.application.compare import execute_comparison
from backend.app.intelligence.robustness import summarize


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.zone = Zone(id='synthetic', name='Test fixture', latitude=10.55, longitude=-85.5)
        self.request = CompareRequest(zona=self.zone, scenario_id='neutral', k=2,
                                      rotation_ids=['rice_melon', 'rice_sorghum'])
        self.analogs = [AnalogYear(year=year, distance=0) for year in (2000, 2001)]
        self.inputs = []
        for year in (2000, 2001):
            for rotation, crop in [('rice_melon', 'melon'), ('rice_sorghum', 'sorghum')]:
                days = [ClimateDay(date=date(year, 4, day), precipitation_mm=0,
                                   tmin_c=20, tmax_c=30, relative_humidity_pct=70,
                                   wind_speed_2m_m_s=2, solar_radiation_mj_m2_day=18,
                                   et0_mm=4) for day in (1, 2, 3)]
                self.inputs.append(SimulationInput(
                    mock=True, generado=datetime(2026, 11, 14, tzinfo=timezone.utc),
                    zona=self.zone, source_refs=['test-only'], warnings=['synthetic fixture'],
                    scenario_id='neutral', climate=ClimateSeason(year=year, start=days[0].date,
                                                               end=days[-1].date, days=days),
                    soil=SoilProfile(field_capacity_m3_m3=None, wilting_point_m3_m3=None,
                                     rooting_depth_m=None, source_refs=[]),
                    rotation=RotationSchedule(rotation_id=rotation, calendar_status='provisional', cycles=[
                        CropCycle(crop_id='rice', sowing_date=days[0].date, harvest_date=days[0].date,
                                  parameter_set_id=None),
                        CropCycle(crop_id=crop, sowing_date=days[1].date, harvest_date=days[2].date,
                                  parameter_set_id=None)]),
                    assumptions=ModelAssumptions(irrigation_mode='unspecified', irrigation_mm_by_date={},
                                                 initial_soil_water_fraction=None, notes=['test only'])))

    @staticmethod
    def kernel(**kwargs):
        # Synthetic fixture with changing baselines: paired deltas must precede quantiles.
        year = kwargs['climate'].year
        value = 100 if year == 2000 else 200
        if kwargs['rotation'].rotation_id == 'rice_sorghum':
            value += 20 if year == 2000 else -40
        return dict(metrics=dict(crop_water_demand_mm=value, modeled_water_deficit_mm=value,
                                 water_stress_days=1), daily_balance=[], assumptions=['test only'],
                    source_refs=['test-only'], warnings=[], model_version='test-only')

    def test_paired_delta_then_quantiles(self):
        result = execute_comparison(self.request, self.analogs, self.inputs, simulate_rotation=self.kernel)
        delta = result.rotations[1].delta_vs_baseline.modeled_water_deficit_mm
        self.assertEqual((delta.p10, delta.p50, delta.p90), (-34, -10, 14))
        self.assertTrue(result.mock)
        self.assertIn('synthetic fixture', result.warnings)

    def test_different_climate_rejected_before_kernel(self):
        self.inputs[1].climate.days[0].precipitation_mm = 99
        def must_not_run(**kwargs):
            self.fail('kernel ran before validating batch')
        with self.assertRaisesRegex(ValueError, 'identical climate'):
            execute_comparison(self.request, self.analogs, self.inputs, simulate_rotation=must_not_run)

    def test_kernel_mutation_does_not_change_inputs(self):
        def mutating_kernel(**kwargs):
            result = self.kernel(**kwargs)
            kwargs['climate'].days[0].precipitation_mm = 500
            return result
        execute_comparison(self.request, self.analogs, self.inputs, simulate_rotation=mutating_kernel)
        self.assertEqual(self.inputs[0].climate.days[0].precipitation_mm, 0)

    def test_incomplete_batch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'one input'):
            execute_comparison(self.request, self.analogs, self.inputs[:-1], simulate_rotation=self.kernel)

    def test_missing_metric_propagates(self):
        def missing_kernel(**kwargs):
            result = self.kernel(**kwargs)
            if kwargs['climate'].year == 2001:
                result['metrics']['modeled_water_deficit_mm'] = None
            return result
        result = execute_comparison(self.request, self.analogs, self.inputs, simulate_rotation=missing_kernel)
        summary = result.rotations[0].metrics.modeled_water_deficit_mm
        self.assertIsNone(summary.p50)
        self.assertEqual(summary.n, 0)
        self.assertTrue(any('incomplete years' in w for w in result.warnings))

    def test_real_inputs_require_scientific_parameters(self):
        self.inputs[0].mock = False
        with self.assertRaisesRegex(ValueError, 'validated zone'):
            execute_comparison(self.request, self.analogs, self.inputs, simulate_rotation=self.kernel)

    def test_kernel_cannot_return_dates_from_another_year(self):
        def wrong_dates_kernel(**kwargs):
            result = self.kernel(**kwargs)
            result['daily_balance'] = [dict(
                date=date(1999, 4, day), crop_water_demand_mm=1,
                modeled_water_deficit_mm=0, soil_water_storage_mm=5, water_stress=False,
            ) for day in (1, 2, 3)]
            return result
        with self.assertRaisesRegex(ValueError, 'exactly the input climate dates'):
            execute_comparison(self.request, self.analogs, self.inputs, simulate_rotation=wrong_dates_kernel)

    def test_water_stress_days_cannot_exceed_climate_duration(self):
        def excessive_stress_kernel(**kwargs):
            result = self.kernel(**kwargs)
            result['metrics']['water_stress_days'] = 4
            return result
        with self.assertRaisesRegex(ValueError, 'exceed input climate duration'):
            execute_comparison(self.request, self.analogs, self.inputs, simulate_rotation=excessive_stress_kernel)

    def test_versions_cannot_differ_between_years_even_with_matching_pairs(self):
        def changing_version_kernel(**kwargs):
            result = self.kernel(**kwargs)
            result['model_version'] = f"kernel-v{kwargs['climate'].year}"
            return result
        with self.assertRaisesRegex(ValueError, 'same model version'):
            execute_comparison(self.request, self.analogs, self.inputs, simulate_rotation=changing_version_kernel)

    def test_real_run_requires_daily_balance_coverage(self):
        self.zone.validated = True
        for simulation in self.inputs:
            simulation.mock = False
            simulation.rotation.calendar_status = 'confirmed'
            for cycle in simulation.rotation.cycles:
                cycle.parameter_set_id = 'test-parameters'
            simulation.soil.field_capacity_m3_m3 = .3
            simulation.soil.wilting_point_m3_m3 = .1
            simulation.soil.rooting_depth_m = 1
            simulation.assumptions.irrigation_mode = 'rainfed'
            simulation.assumptions.initial_soil_water_fraction = .5
        with self.assertRaisesRegex(ValueError, 'exactly the input climate dates'):
            execute_comparison(self.request, self.analogs, self.inputs, simulate_rotation=self.kernel)

    def test_quantiles(self):
        self.assertEqual(summarize([10]).p50, 10)
        self.assertEqual(summarize([]).n, 0)
        self.assertIsNone(summarize([10, None]).p50)


if __name__ == '__main__':
    unittest.main()
