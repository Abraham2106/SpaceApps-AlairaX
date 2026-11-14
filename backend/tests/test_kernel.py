"""Kernel FAO-56 (Justin) contra el contrato M1 de Abe."""

from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from backend.app.api.schemas.contracts import (
    ClimateDay, ClimateSeason, CompareResponse, DailyBalance, Metrics, ModelAssumptions, SoilProfile,
)
from backend.app.simulation.kernel import (
    SEASONAL_ETC_RANGE_MM, scale_stage_days, simulate_rotation, simulate_rotation_detailed,
    template_rotation,
)
from backend.app.simulation.version import MODEL_VERSION
from scripts.export_contracts import ZONE, make_fixture
from scripts.export_et0 import build_et0
from scripts.run_comparison import compare_from_analogs

ROOT = Path(__file__).resolve().parents[2]
CLIMATE_DIR = ROOT / 'datasets' / 'processed' / 'climate'
ET0_FILE = ROOT / 'datasets' / 'processed' / 'et0' / 'et0_10.55_-85.5.json'
ROTATIONS = [('rice_melon', 'melon'), ('rice_legume', 'legume'), ('rice_sorghum', 'sorghum')]


def _call(simulation, kernel=simulate_rotation):
    return kernel(climate=simulation.climate, soil=simulation.soil,
                  rotation=simulation.rotation, assumptions=simulation.assumptions)


def _mock_inputs(years=(2000, 2001)):
    inputs = []
    for year in years:
        for rotation_id, crop_id in ROTATIONS:
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
            inputs.append(simulation)
    return inputs


def _analog_document(years=(2000, 2001)):
    return {
        '_mock': True, 'zona': ZONE.model_dump(mode='json'), 'source_refs': [], 'warnings': [],
        'scenarios': {'neutral': {
            '_mock': True, 'status': 'available', 'k': len(years),
            'neighbors': [{'year': y, 'distance': 0.1 * (i + 1)} for i, y in enumerate(years)],
        }},
    }


class KernelContractTests(unittest.TestCase):
    def test_output_matches_contract_models(self):
        result = _call(make_fixture())
        self.assertEqual(set(result), {'metrics', 'daily_balance', 'assumptions', 'source_refs',
                                       'warnings', 'model_version'})
        self.assertEqual(result['model_version'], MODEL_VERSION)
        Metrics.model_validate(result['metrics'])
        rows = [DailyBalance.model_validate(row) for row in result['daily_balance']]
        self.assertEqual([r.date for r in rows], [d.date for d in make_fixture().climate.days])
        self.assertIsInstance(result['metrics']['water_stress_days'], int)
        # Sin θ ni ET0 en el mock: el kernel usa fallbacks y lo declara.
        self.assertTrue(any('loam' in w for w in result['warnings']))

    def test_fallow_days_have_no_stress_flag(self):
        rows = _call(make_fixture())['daily_balance']
        by_date = {row['date']: row for row in rows}
        self.assertIsNone(by_date[date(2015, 4, 15)]['water_stress'])
        self.assertIsNotNone(by_date[date(2015, 6, 15)]['water_stress'])

    def test_three_rotations_distinct_and_deterministic(self):
        inputs = _mock_inputs(years=(2015,))
        first = [_call(i)['metrics'] for i in inputs]
        second = [_call(i)['metrics'] for i in inputs]
        self.assertEqual(first, second)
        self.assertEqual(len({json.dumps(m, sort_keys=True) for m in first}), 3)
        # compare_runs exige assumptions idénticos entre rotaciones pareadas.
        self.assertEqual(len({tuple(_call(i)['assumptions']) for i in inputs}), 1)

    def test_long_climate_gap_nulls_metrics(self):
        simulation = make_fixture()
        for day in simulation.climate.days[100:110]:
            day.precipitation_mm = None
        result = _call(simulation)
        self.assertEqual(result['metrics'], {'crop_water_demand_mm': None,
                                             'modeled_water_deficit_mm': None,
                                             'water_stress_days': None})
        self.assertEqual(len(result['daily_balance']), len(simulation.climate.days))
        self.assertIsNone(result['daily_balance'][105]['crop_water_demand_mm'])

    def test_short_gap_is_filled_with_warning(self):
        simulation = make_fixture()
        simulation.climate.days[100].precipitation_mm = None
        result = _call(simulation)
        self.assertIsNotNone(result['metrics']['crop_water_demand_mm'])
        self.assertTrue(any('0' in w and 'lluvia' in w.lower() for w in result['warnings'])
                        or len(result['warnings']) > len(_call(make_fixture())['warnings']))

    def test_scheduled_irrigation_reduces_deficit(self):
        simulation = make_fixture()
        base = _call(simulation)['metrics']
        simulation.assumptions = ModelAssumptions(
            irrigation_mode='scheduled', initial_soil_water_fraction=None, notes=[],
            irrigation_mm_by_date={date(2015, 10, d): 30.0 for d in range(1, 31, 3)})
        irrigated = _call(simulation)['metrics']
        self.assertLess(irrigated['modeled_water_deficit_mm'], base['modeled_water_deficit_mm'])

    def test_detailed_adds_irrigation_requirement_only_for_melon(self):
        inputs = _mock_inputs(years=(2015,))
        requirements = {i.rotation.rotation_id: _call(i, simulate_rotation_detailed)['irrigation_requirement_mm']
                        for i in inputs}
        self.assertGreater(requirements['rice_melon'], 0)
        self.assertEqual(requirements['rice_legume'], 0)
        self.assertEqual(requirements['rice_sorghum'], 0)

    def test_scale_stage_days_preserves_total(self):
        for duration in (60, 92, 123, 150):
            scaled = scale_stage_days([30, 30, 60, 30], duration)
            self.assertEqual(sum(scaled), duration)
            self.assertTrue(all(s >= 1 for s in scaled))


class KernelPipelineTests(unittest.TestCase):
    def test_mock_inputs_run_through_execute_comparison(self):
        result = compare_from_analogs(_analog_document(), 'neutral', _mock_inputs(),
                                      simulate_rotation=simulate_rotation)
        self.assertTrue(result.mock)
        self.assertEqual(len(result.rotations), 3)
        self.assertTrue(all(len(r.runs) == 2 for r in result.rotations))
        self.assertTrue(all(run.model_version == MODEL_VERSION
                            for r in result.rotations for run in r.runs))

    def test_run_comparison_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'analogs.json').write_text(json.dumps(_analog_document()), encoding='utf-8')
            (tmp / 'inputs.json').write_text(json.dumps(
                [i.model_dump(mode='json', by_alias=True) for i in _mock_inputs()]), encoding='utf-8')
            output = tmp / 'out' / 'comparison.json'
            completed = subprocess.run(
                [sys.executable, '-m', 'scripts.run_comparison', '--analogs', str(tmp / 'analogs.json'),
                 '--scenario', 'neutral', '--inputs', str(tmp / 'inputs.json'),
                 '--kernel', 'backend.app.simulation.kernel:simulate_rotation',
                 '--output', str(output), '--allow-mock'],
                cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(completed.returncode, 0, completed.stderr)
            loaded = CompareResponse.model_validate_json(output.read_text(encoding='utf-8'))
            self.assertEqual(len(loaded.rotations), 3)


@unittest.skipUnless(ET0_FILE.exists() and CLIMATE_DIR.exists(), 'datos POWER procesados no disponibles')
class KernelRealSeasonTests(unittest.TestCase):
    """Temporadas POWER reales (mayo Y – abril Y+1): ETc por ciclo en rango FAO o con aviso."""

    @classmethod
    def setUpClass(cls):
        cls.et0 = json.loads(ET0_FILE.read_text(encoding='utf-8'))['values']

    def season(self, year):
        rows = []
        for y in (year, year + 1):
            path = CLIMATE_DIR / f'power_10.55_-85.5_{y}-01-01_{y}-12-31.json'
            rows += json.loads(path.read_text(encoding='utf-8'))['days']
        start, end = date(year, 5, 1), date(year + 1, 4, 30)
        days = [ClimateDay(**(r | {'et0_mm': self.et0[r['date']]})) for r in rows
                if start <= date.fromisoformat(r['date']) <= end]
        return ClimateSeason(year=year, start=start, end=end, days=days)

    def test_seasonal_etc_in_fao_range_or_warned(self):
        soil = SoilProfile(field_capacity_m3_m3=0.30, wilting_point_m3_m3=0.15,
                           rooting_depth_m=None, source_refs=['test'])
        assumptions = ModelAssumptions(irrigation_mode='rainfed', irrigation_mm_by_date={},
                                       initial_soil_water_fraction=0.5, notes=[])
        for year in (2015, 2023, 2013):
            climate = self.season(year)
            for rotation_id, _ in ROTATIONS:
                rotation = template_rotation(rotation_id, year, sowing_dates={
                    'rice': date(year, 5, 15), 'legume': date(year, 10, 15),
                    'sorghum': date(year, 10, 15)})
                with self.subTest(year=year, rotation=rotation_id):
                    result = simulate_rotation_detailed(climate=climate, soil=soil,
                                                        rotation=rotation, assumptions=assumptions)
                    Metrics.model_validate(result['metrics'])
                    for crop in result['per_crop']:
                        etc = crop['crop_water_demand_mm']
                        self.assertIsNotNone(etc)
                        low, high = SEASONAL_ETC_RANGE_MM[crop['crop_id']]
                        if not low <= etc <= high:
                            self.assertTrue(any(w.startswith(f"{crop['crop_id']}: ETc estacional")
                                                for w in result['warnings']))


@unittest.skipUnless(CLIMATE_DIR.exists(), 'datos POWER procesados no disponibles')
class ExportEt0Tests(unittest.TestCase):
    def test_export_is_unreviewed_and_matches_climate_zone(self):
        files = [CLIMATE_DIR / 'power_10.55_-85.5_2015-01-01_2015-12-31.json',
                 CLIMATE_DIR / 'power_10.55_-85.5_1981-01-01_1981-12-31.json']
        document = build_et0(files)
        climate = json.loads(files[0].read_text(encoding='utf-8'))
        self.assertFalse(document['reviewed'])
        self.assertIsNone(document['reviewed_by'])
        self.assertEqual(document['units'], 'mm/day')
        self.assertEqual(document['zona'], climate['zona'])
        self.assertEqual(document['_mock'], climate['_mock'])
        self.assertEqual(len(document['values']), 365 + 365)
        values_2015 = [v for k, v in document['values'].items() if k.startswith('2015')]
        self.assertTrue(all(v is not None and 0 < v < 12 for v in values_2015))
        # 1981 sin radiación en POWER: null, nunca cero.
        self.assertTrue(any(v is None for k, v in document['values'].items() if k.startswith('1981')))
        self.assertNotIn(0.0, [v for k, v in document['values'].items() if k.startswith('1981')])

    def test_manual_elevation_is_warned(self):
        document = build_et0([CLIMATE_DIR / 'power_10.55_-85.5_2015-01-01_2015-12-31.json'],
                             elevation_m=100.0)
        self.assertEqual(document['elevation_source'], 'manual --elevation-m')
        self.assertTrue(document['warnings'])


if __name__ == '__main__':
    unittest.main()
