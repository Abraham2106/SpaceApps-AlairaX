"""Fase 5 (tarea 3.5): casos de QA del kernel FAO-56 y snapshot de regresión.

Regenerar el snapshot tras un cambio científico intencional:
    UPDATE_SNAPSHOTS=1 python -m pytest backend/tests/test_kernel_qa.py
"""

from datetime import date, timedelta
import json
import math
import os
from pathlib import Path
import unittest

from backend.app.api.schemas.contracts import (
    ClimateDay, ClimateSeason, CropCycle, ModelAssumptions, RotationSchedule, SoilProfile,
)
from backend.app.simulation.kernel import (
    _default_crops, scale_stage_days, simulate_rotation, simulate_rotation_detailed,
    template_rotation,
)
from backend.app.simulation.contract import CropLibrary, CropParameters
from scripts.export_contracts import make_fixture

ROOT = Path(__file__).resolve().parents[2]
CLIMATE_DIR = ROOT / 'datasets' / 'processed' / 'climate'
ET0_FILE = ROOT / 'datasets' / 'processed' / 'et0' / 'et0_10.55_-85.5.json'
SNAPSHOT = Path(__file__).parent / 'snapshots' / 'kernel_metrics_2015.json'
QA_CASES = ROOT / 'research' / 'qa_cases.md'
ET0 = 5.0


def _run(simulation, kernel=simulate_rotation, **kwargs):
    return kernel(climate=simulation.climate, soil=simulation.soil,
                  rotation=simulation.rotation, assumptions=simulation.assumptions, **kwargs)


def _constant_et0_fixture():
    """Fixture mock con ET0 fija: ETc/ET0 = Kc diario, sin estrés (riego no aplica)."""
    simulation = make_fixture()
    for day in simulation.climate.days:
        day.et0_mm = ET0
    return simulation


def _kc_by_date(result):
    return {row['date']: row['crop_water_demand_mm'] / ET0 for row in result['daily_balance']}


class StageAndCropChangeTests(unittest.TestCase):
    """Rice 05-01..08-31 (123 d → etapas [25, 25, 49, 24]); melón 10-01..12-31 ([19, 27, 31, 15])."""

    @classmethod
    def setUpClass(cls):
        cls.crops = _default_crops().crops
        cls.kc = _kc_by_date(_run(_constant_et0_fixture()))

    def test_initial_stage_uses_kc_ini(self):
        self.assertAlmostEqual(self.kc[date(2015, 5, 10)], self.crops['rice'].kc_ini, places=3)

    def test_development_stage_interpolates_between_kc_ini_and_kc_mid(self):
        rice = self.crops['rice']
        value = self.kc[date(2015, 6, 7)]  # día 38: mitad de desarrollo
        self.assertGreater(value, rice.kc_ini)
        self.assertLess(value, rice.kc_mid)

    def test_mid_stage_uses_kc_mid(self):
        self.assertAlmostEqual(self.kc[date(2015, 7, 15)], self.crops['rice'].kc_mid, places=3)

    def test_late_stage_ends_near_kc_end(self):
        rice = self.crops['rice']
        self.assertAlmostEqual(self.kc[date(2015, 8, 31)], rice.kc_end, delta=0.02)
        self.assertLess(self.kc[date(2015, 8, 31)], self.kc[date(2015, 8, 10)])

    def test_crop_change_goes_through_fallow_and_restarts_kc(self):
        self.assertAlmostEqual(self.kc[date(2015, 9, 15)], 0.15, places=3)  # D5
        self.assertAlmostEqual(self.kc[date(2015, 10, 5)], self.crops['melon'].kc_ini, places=3)
        self.assertAlmostEqual(self.kc[date(2015, 4, 15)], 0.15, places=3)  # antes del arroz

    def test_stage_boundaries_are_continuous(self):
        days = sorted(self.kc)
        jumps = [abs(self.kc[b] - self.kc[a]) for a, b in zip(days, days[1:])
                 if date(2015, 5, 2) <= b <= date(2015, 8, 31)]
        self.assertLess(max(jumps), 0.02)


class MissingDataTests(unittest.TestCase):
    def test_short_et0_gap_is_interpolated_between_neighbours(self):
        simulation = make_fixture()
        for day in simulation.climate.days[60:62]:
            day.tmax_c = None
        result = _run(simulation)
        rows = result['daily_balance']
        self.assertTrue(any('interpolado linealmente' in w for w in result['warnings']))
        self.assertIsNotNone(result['metrics']['crop_water_demand_mm'])
        self.assertTrue(all(rows[i]['crop_water_demand_mm'] is not None for i in range(59, 63)))

    def test_short_rain_gap_is_zero_filled(self):
        simulation = make_fixture()
        simulation.climate.days[30].precipitation_mm = None
        result = _run(simulation)
        self.assertTrue(any('rellenado con 0 mm' in w for w in result['warnings']))
        self.assertIsNotNone(result['metrics']['water_stress_days'])

    def test_gap_at_season_edge_without_neighbours_blocks_metrics(self):
        simulation = make_fixture()
        for day in simulation.climate.days:
            day.tmax_c = None
        result = _run(simulation)
        self.assertIsNone(result['metrics']['crop_water_demand_mm'])
        self.assertTrue(all(r['crop_water_demand_mm'] is None for r in result['daily_balance']))

    def test_null_soil_falls_back_to_loam_and_warns(self):
        simulation = make_fixture()
        self.assertIsNone(simulation.soil.field_capacity_m3_m3)
        result = _run(simulation)
        self.assertTrue(any('loam' in w for w in result['warnings']))
        self.assertIsNotNone(result['metrics']['crop_water_demand_mm'])

    def test_null_initial_fraction_starts_at_field_capacity(self):
        simulation = make_fixture()
        self.assertIsNone(simulation.assumptions.initial_soil_water_fraction)
        result = _run(simulation)
        self.assertTrue(any('Dr0 = 0' in w for w in result['warnings']))


class SoilAndParameterTests(unittest.TestCase):
    def test_shallow_soil_limits_root_depth(self):
        simulation = make_fixture()
        simulation.soil = SoilProfile(field_capacity_m3_m3=0.30, wilting_point_m3_m3=0.15,
                                      rooting_depth_m=0.4, source_refs=['qa'])
        result = _run(simulation, simulate_rotation_detailed)
        self.assertTrue(all(c['root_depth_m'] == 0.4 for c in result['per_crop']))
        self.assertTrue(any('Zr limitada por el suelo' in w for w in result['warnings']))

    def test_shallow_soil_stresses_more_than_deep_soil(self):
        deep, shallow = make_fixture(), make_fixture()
        for simulation, depth in ((deep, None), (shallow, 0.3)):
            simulation.soil = SoilProfile(field_capacity_m3_m3=0.30, wilting_point_m3_m3=0.15,
                                          rooting_depth_m=depth, source_refs=['qa'])
        self.assertGreater(_run(shallow)['metrics']['water_stress_days'],
                           _run(deep)['metrics']['water_stress_days'])

    def test_null_parameter_set_uses_default_with_warning(self):
        result = _run(make_fixture())
        self.assertTrue(any("parameter_set_id null; se usa el default 'rice'" in w
                            for w in result['warnings']))

    def test_unknown_parameter_set_raises(self):
        simulation = make_fixture()
        simulation.rotation.cycles[0].parameter_set_id = 'no_existe'
        with self.assertRaises(KeyError):
            _run(simulation)

    def test_incomplete_parameters_run_cycle_as_fallow(self):
        crops = _default_crops().model_copy(deep=True)  # la librería por defecto está cacheada
        crops.crops['melon'] = crops.crops['melon'].model_copy(update={'kc_mid': None})
        result = _run(make_fixture(), simulate_rotation_detailed, crops=crops)
        self.assertTrue(any('parámetros faltantes para melon' in w for w in result['warnings']))
        melon = next(c for c in result['per_crop'] if c['crop_id'] == 'melon')
        self.assertFalse(melon['simulated'])
        self.assertIsNone(melon['crop_water_demand_mm'])

    def test_scale_stage_days_rejects_too_short_cycles(self):
        with self.assertRaises(ValueError):
            scale_stage_days([30, 30, 60, 30], 3)

    def test_scale_stage_days_keeps_every_stage_on_short_cycles(self):
        for duration in range(4, 20):
            scaled = scale_stage_days([5, 5, 5, 100], duration)
            self.assertEqual(sum(scaled), duration)
            self.assertTrue(all(s >= 1 for s in scaled), scaled)


class LeapSeasonTests(unittest.TestCase):
    def test_cycle_across_february_29(self):
        start, end = date(2016, 1, 1), date(2016, 6, 30)
        days = [ClimateDay(date=start + timedelta(days=i), precipitation_mm=2.0 if i % 4 == 0 else 0.0,
                           tmin_c=22.0, tmax_c=33.0, relative_humidity_pct=65.0, wind_speed_2m_m_s=2.5,
                           solar_radiation_mj_m2_day=20.0, et0_mm=None)
                for i in range((end - start).days + 1)]
        self.assertEqual(len(days), 182)
        climate = ClimateSeason(year=2016, start=start, end=end, days=days)
        rotation = RotationSchedule(rotation_id='rice_melon', calendar_status='provisional', cycles=[
            CropCycle(crop_id='rice', sowing_date=date(2016, 1, 15), harvest_date=date(2016, 3, 31),
                      parameter_set_id='rice'),
            CropCycle(crop_id='melon', sowing_date=date(2016, 4, 10), harvest_date=date(2016, 6, 30),
                      parameter_set_id='melon'),
        ])
        soil = SoilProfile(field_capacity_m3_m3=0.30, wilting_point_m3_m3=0.15,
                           rooting_depth_m=None, source_refs=['qa'])
        assumptions = ModelAssumptions(irrigation_mode='rainfed', irrigation_mm_by_date={},
                                       initial_soil_water_fraction=1.0, notes=[])
        result = simulate_rotation_detailed(climate=climate, soil=soil, rotation=rotation,
                                            assumptions=assumptions)
        dates = [row['date'] for row in result['daily_balance']]
        self.assertIn(date(2016, 2, 29), dates)
        self.assertEqual(len(dates), 182)
        self.assertIsNotNone(result['daily_balance'][dates.index(date(2016, 2, 29))]['water_stress'])
        rice = result['per_crop'][0]
        self.assertEqual(sum(rice['stage_days']), 77)  # 15-ene..31-mar de un año bisiesto
        self.assertIsNotNone(rice['crop_water_demand_mm'])


def _hand_case(rain, kc, stage_days, root_depth_m, p, initial_fraction, crop_days):
    """Corre el kernel con el cultivo de juguete de research/qa_cases.md (suelo θfc 0.30, θwp 0.15, ET0 5.0).

    El segundo ciclo (melón, sin parámetros) cae fuera de la ventana de clima: solo cumple la
    regla del contrato de que ``rice_melon`` lleve arroz y melón.
    """
    start = date(2020, 5, 1)
    days = [ClimateDay(date=start + timedelta(days=i), precipitation_mm=value, tmin_c=22.0, tmax_c=33.0,
                       relative_humidity_pct=65.0, wind_speed_2m_m_s=2.5, solar_radiation_mj_m2_day=20.0,
                       et0_mm=ET0) for i, value in enumerate(rain)]
    climate = ClimateSeason(year=2020, start=start, end=start + timedelta(days=len(rain) - 1), days=days)
    toy = CropParameters(display_name='qa toy', kc_ini=kc[0], kc_mid=kc[1], kc_end=kc[2],
                         stage_days=stage_days, root_depth_max_m=root_depth_m, p_depletion=p)
    crops = CropLibrary(version='qa', crops={'qa_toy': toy, 'qa_null': CropParameters(display_name='sin parametros')})
    rotation = RotationSchedule(rotation_id='rice_melon', calendar_status='provisional', cycles=[
        CropCycle(crop_id='rice', sowing_date=start, harvest_date=start + timedelta(days=crop_days - 1),
                  parameter_set_id='qa_toy'),
        CropCycle(crop_id='melon', sowing_date=date(2021, 1, 1), harvest_date=date(2021, 1, 20),
                  parameter_set_id='qa_null'),
    ])
    soil = SoilProfile(field_capacity_m3_m3=0.30, wilting_point_m3_m3=0.15, rooting_depth_m=None,
                       source_refs=['qa'])
    assumptions = ModelAssumptions(irrigation_mode='rainfed', irrigation_mm_by_date={},
                                   initial_soil_water_fraction=initial_fraction, notes=[])
    return simulate_rotation_detailed(climate=climate, soil=soil, rotation=rotation,
                                      assumptions=assumptions, crops=crops)


class AntHandCalculatedCasesTests(unittest.TestCase):
    """Los 3 casos calculados a mano de research/qa_cases.md (tarea 2.4).

    Los valores esperados salen de la aritmética exacta de ese documento (Eq. 66, 82-85 de FAO-56
    y las convenciones D3/D5), no de la salida del kernel. Tolerancia: el kernel redondea a 4 decimales.
    """

    def assert_series(self, result, field, expected):
        actual = [row[field] for row in result['daily_balance']]
        self.assertEqual(len(actual), len(expected))
        for index, (got, want) in enumerate(zip(actual, expected)):
            if want is None:
                self.assertIsNone(got, f'día {index}')
            else:
                self.assertAlmostEqual(got, want, places=3, msg=f'{field}, día {index}')

    def test_case_1(self):
        """Caso 1: interpolación de Kc por etapas, sin estrés, lluvia de 10 mm el día 3."""
        result = _hand_case([0, 0, 10, 0, 0, 0, 0, 0], (0.4, 1.2, 0.6), [2, 2, 2, 2], 1.0, 0.5, 0.8, 8)
        self.assert_series(result, 'crop_water_demand_mm', [2, 2, 2, 4, 6, 6, 6, 4.5])
        self.assert_series(result, 'modeled_water_deficit_mm', [0] * 8)
        self.assert_series(result, 'soil_water_storage_mm', [118, 116, 124, 120, 114, 108, 102, 97.5])
        self.assert_series(result, 'water_stress', [False] * 8)
        self.assertAlmostEqual(result['metrics']['crop_water_demand_mm'], 32.5, places=3)
        self.assertAlmostEqual(result['metrics']['modeled_water_deficit_mm'], 0.0, places=3)
        self.assertEqual(result['metrics']['water_stress_days'], 0)

    def test_case_2(self):
        """Caso 2: Ks < 1 (Eq. 84), escorrentía D3 con 80 mm y percolación profunda."""
        result = _hand_case([0, 0, 0, 0, 80, 0], (1.0, 1.0, 1.0), [2, 1, 2, 1], 0.4, 0.5, 0.6, 6)
        self.assert_series(result, 'crop_water_demand_mm', [5] * 6)
        self.assert_series(result, 'modeled_water_deficit_mm',
                           [0, 0, 2 / 3, 25 / 18, 215 / 108, 0])
        self.assert_series(result, 'soil_water_storage_mm', [31, 26, 65 / 3, 325 / 18, 60, 55])
        self.assert_series(result, 'water_stress', [False, False, True, True, True, False])
        self.assertAlmostEqual(result['metrics']['crop_water_demand_mm'], 30.0, places=3)
        self.assertAlmostEqual(result['metrics']['modeled_water_deficit_mm'], 437 / 108, places=3)
        self.assertEqual(result['metrics']['water_stress_days'], 3)

    def test_case_3(self):
        """Caso 3: cambio a barbecho con reescalado de Dr por Zr (D5), piso en 0 mm y percolación."""
        result = _hand_case([0, 20, 0, 0, 0, 30, 0], (0.8, 0.8, 0.8), [1, 1, 1, 1], 0.6, 0.5, 0.5, 4)
        self.assert_series(result, 'crop_water_demand_mm', [4, 4, 4, 4, 0.75, 0.75, 0.75])
        self.assert_series(result, 'modeled_water_deficit_mm', [0, 16 / 45, 0, 0, 0, 0, 0])
        self.assert_series(result, 'soil_water_storage_mm',
                           [41, 2581 / 45, 2401 / 45, 2221 / 45, 11.588889, 22.5, 21.75])
        self.assert_series(result, 'water_stress', [False, True, False, False, None, None, None])
        # Solo cuentan los 4 días de cultivo; el barbecho (0.75 mm/día) no suma a las métricas.
        self.assertAlmostEqual(result['metrics']['crop_water_demand_mm'], 16.0, places=3)
        self.assertAlmostEqual(result['metrics']['modeled_water_deficit_mm'], 16 / 45, places=3)
        self.assertEqual(result['metrics']['water_stress_days'], 1)
        self.assertTrue(any('reescalado' in w for w in result['warnings']))


@unittest.skipUnless(ET0_FILE.exists() and CLIMATE_DIR.exists(), 'datos POWER procesados no disponibles')
class RegressionSnapshotTests(unittest.TestCase):
    """Métricas de las 3 rotaciones en la temporada real 2015 (mayo 2015 – abril 2016)."""

    def current(self):
        et0 = json.loads(ET0_FILE.read_text(encoding='utf-8'))['values']
        rows = []
        for y in (2015, 2016):
            rows += json.loads((CLIMATE_DIR / f'power_10.55_-85.5_{y}-01-01_{y}-12-31.json')
                               .read_text(encoding='utf-8'))['days']
        start, end = date(2015, 5, 1), date(2016, 4, 30)
        days = [ClimateDay(**(r | {'et0_mm': et0[r['date']]})) for r in rows
                if start <= date.fromisoformat(r['date']) <= end]
        climate = ClimateSeason(year=2015, start=start, end=end, days=days)
        soil = SoilProfile(field_capacity_m3_m3=0.30, wilting_point_m3_m3=0.15,
                           rooting_depth_m=None, source_refs=['qa'])
        assumptions = ModelAssumptions(irrigation_mode='rainfed', irrigation_mm_by_date={},
                                       initial_soil_water_fraction=0.5, notes=[])
        out = {}
        for rotation_id in ('rice_melon', 'rice_legume', 'rice_sorghum'):
            rotation = template_rotation(rotation_id, 2015, sowing_dates={
                'rice': date(2015, 5, 15), 'legume': date(2015, 10, 15), 'sorghum': date(2015, 10, 15)})
            result = simulate_rotation_detailed(climate=climate, soil=soil, rotation=rotation,
                                                assumptions=assumptions)
            out[rotation_id] = {
                'metrics': result['metrics'],
                'irrigation_requirement_mm': result['irrigation_requirement_mm'],
                'per_crop': {c['crop_id']: c['crop_water_demand_mm'] for c in result['per_crop']},
                'model_version': result['model_version'],
            }
        return out

    def test_metrics_match_snapshot(self):
        current = self.current()
        if os.environ.get('UPDATE_SNAPSHOTS') or not SNAPSHOT.exists():
            SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
            SNAPSHOT.write_text(json.dumps(current, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            if os.environ.get('UPDATE_SNAPSHOTS'):
                self.skipTest('snapshot regenerado')
        expected = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
        self.assertEqual(set(current), set(expected))
        for rotation_id, values in expected.items():
            got = current[rotation_id]
            self.assertEqual(got['model_version'], values['model_version'], rotation_id)
            self.assertEqual(got['metrics']['water_stress_days'], values['metrics']['water_stress_days'])
            for key in ('crop_water_demand_mm', 'modeled_water_deficit_mm'):
                self.assertTrue(math.isclose(got['metrics'][key], values['metrics'][key], abs_tol=1e-3),
                                f'{rotation_id}.{key}: {got["metrics"][key]} != {values["metrics"][key]}')
            self.assertTrue(math.isclose(got['irrigation_requirement_mm'],
                                         values['irrigation_requirement_mm'], abs_tol=1e-3))
            for crop, etc in values['per_crop'].items():
                self.assertTrue(math.isclose(got['per_crop'][crop], etc, abs_tol=1e-3), f'{rotation_id}.{crop}')


if __name__ == '__main__':
    unittest.main()
