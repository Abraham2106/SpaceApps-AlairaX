"""P1 científicos del kernel (Fase 7): estrés térmico (3.6) y sensibilidad (3.7)."""

from datetime import date
import tempfile
from pathlib import Path
import unittest

from backend.app.simulation.contract import SoilWaterProfile
from backend.app.simulation.kernel import (
    HEAT_SENSITIVE_STAGE, _default_crops, simulate_rotation, simulate_rotation_detailed,
)
from scripts import sensitivity
from scripts.export_contracts import make_fixture


def _call(simulation, crops=None, kernel=simulate_rotation_detailed):
    return kernel(climate=simulation.climate, soil=simulation.soil, rotation=simulation.rotation,
                  assumptions=simulation.assumptions, crops=crops)


def _with_tmax(tmax, *, missing_on=None):
    simulation = make_fixture()
    for day in simulation.climate.days:
        day.tmin_c = 20.0
        day.tmax_c = None if missing_on is not None and day.date == missing_on else tmax
    return simulation


def _rice(result):
    return next(c for c in result["per_crop"] if c["crop_id"] == "rice")


def _mid_dates(cycle):
    ini, dev, mid, _ = cycle["stage_days"]
    start = cycle["sowing_date"].toordinal() + ini + dev
    return [date.fromordinal(start + i) for i in range(mid)]


class HeatStressTests(unittest.TestCase):
    def test_hot_season_counts_every_mid_stage_day(self):
        result = _call(_with_tmax(36.0))
        rice = _rice(result)
        self.assertEqual(HEAT_SENSITIVE_STAGE, "mid")
        self.assertEqual(rice["heat_threshold_c"], 35.0)
        self.assertEqual(rice["heat_stress_days"], rice["stage_days"][2])
        self.assertEqual(result["heat_stress_days"], rice["heat_stress_days"])

    def test_threshold_is_inclusive_and_cool_season_is_zero(self):
        self.assertEqual(_call(_with_tmax(30.0))["heat_stress_days"], 0)
        exact = _call(_with_tmax(35.0))
        self.assertEqual(exact["heat_stress_days"], _rice(exact)["stage_days"][2])

    def test_crops_without_threshold_stay_null(self):
        result = _call(_with_tmax(36.0))
        others = [c for c in result["per_crop"] if c["crop_id"] != "rice"]
        self.assertTrue(others)
        for crop in others:
            self.assertIsNone(crop["heat_threshold_c"])
            self.assertIsNone(crop["heat_stress_days"])

    def test_null_threshold_gives_null_metric(self):
        crops = _default_crops().model_copy(deep=True)
        crops.crops["rice"] = crops.crops["rice"].model_copy(update={"heat_threshold_c": None})
        result = _call(_with_tmax(36.0), crops=crops)
        self.assertIsNone(_rice(result)["heat_stress_days"])
        self.assertIsNone(result["heat_stress_days"])
        self.assertEqual(_default_crops().crops["rice"].heat_threshold_c, 35.0)

    def test_missing_tmax_in_mid_stage_is_null_with_warning(self):
        rice = _rice(_call(_with_tmax(36.0)))
        missing = _mid_dates(rice)[5]
        result = _call(_with_tmax(36.0, missing_on=missing))
        self.assertIsNone(_rice(result)["heat_stress_days"])
        self.assertTrue(any("tmax faltante" in w for w in result["warnings"]))

    def test_contract_output_unchanged(self):
        result = _call(_with_tmax(36.0), kernel=simulate_rotation)
        self.assertNotIn("heat_stress_days", result)
        self.assertNotIn("heat_stress_days", result["metrics"])


class SensitivityHelpersTests(unittest.TestCase):
    def test_scale_kc_does_not_touch_cached_library(self):
        base = _default_crops()
        scaled = sensitivity.scale_kc(base, 1.1)
        self.assertAlmostEqual(scaled.crops["rice"].kc_mid, base.crops["rice"].kc_mid * 1.1)
        self.assertEqual(base.crops["rice"].kc_mid, 1.20)
        self.assertIs(sensitivity.scale_kc(base, 1.0), base)

    def test_scale_rain_keeps_nulls(self):
        climate = make_fixture().climate
        climate.days[3].precipitation_mm = None
        wetter = sensitivity.scale_rain(climate, 1.28)
        self.assertIsNone(wetter.days[3].precipitation_mm)
        index = next(i for i, d in enumerate(climate.days) if d.precipitation_mm)
        self.assertAlmostEqual(wetter.days[index].precipitation_mm,
                               climate.days[index].precipitation_mm * 1.28)

    def test_soil_cases_keep_fc_above_wp(self):
        base = SoilWaterProfile.from_soilgrids(None, None, "loam")
        for case in sensitivity.CASES:
            soil = sensitivity.soil_for(case, base)
            self.assertGreater(soil.field_capacity_m3_m3, soil.wilting_point_m3_m3)
        with self.assertRaises(ValueError):
            sensitivity.soil_for(sensitivity.Case("bad", "x", "x", fc=0.4), base)

    def test_ranking_groups_ties_and_skips_nulls(self):
        self.assertEqual(sensitivity._ranking({"rice_melon": 2.0, "rice_legume": 1.0, "rice_sorghum": 2.0}),
                         (1, 0, 1))
        self.assertIsNone(sensitivity._ranking({"rice_melon": None, "rice_legume": 1.0, "rice_sorghum": 2.0}))


@unittest.skipUnless(sensitivity.ET0_FILE.exists() and sensitivity.CLIMATE_DIR.exists(),
                     "datos POWER procesados no disponibles")
class SensitivityRunTests(unittest.TestCase):
    def test_one_season_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            sensitivity.main(["--years", "2015", "--output-dir", tmp])
            csv_text = (Path(tmp) / "sensitivity.csv").read_text(encoding="utf-8")
            summary = (Path(tmp) / "sensitivity.md").read_text(encoding="utf-8")
        lines = csv_text.strip().splitlines()
        self.assertEqual(len(lines) - 1, len(sensitivity.CASES) * 3 * len(sensitivity.METRICS))
        base_rows = [line for line in lines[1:] if line.startswith("base,")]
        self.assertTrue(base_rows)
        self.assertTrue(all(line.split(",")[7] == "" or float(line.split(",")[7]) == 0
                            for line in base_rows))
        for case in sensitivity.CASES[1:]:
            self.assertIn(case.label, summary)

    def test_directions_match_physics(self):
        et0 = __import__("json").loads(sensitivity.ET0_FILE.read_text(encoding="utf-8"))["values"]
        runs = sensitivity.run_all([2015], et0)
        deficit = {r.case.case_id: sum(x.values["modeled_water_deficit_mm"] for x in runs
                                       if x.case.case_id == r.case.case_id) for r in runs}
        self.assertGreater(deficit["kc_+10"], deficit["base"])
        self.assertLess(deficit["kc_-10"], deficit["base"])
        self.assertGreater(deficit["rain_-28"], deficit["base"])
        self.assertLess(deficit["rain_+28"], deficit["base"])
        self.assertGreater(deficit["fc_-20"], deficit["base"])


if __name__ == "__main__":
    unittest.main()
