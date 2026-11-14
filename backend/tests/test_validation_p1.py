"""Fase 8: backtest de análogos (4.6) y lluvia CHIRPS v3 (4.8). Sin red."""

import random
import unittest

from scripts import backtest, ingest_chirps, rain_bias


def _lzw_encode(data: bytes) -> bytes:
    """Codificador LZW de TIFF mínimo (MSB primero, cambio anticipado), solo para probar el decodificador."""
    codes, width, emitted = [], 9, 0

    def emit(code: int) -> None:
        nonlocal width, emitted
        codes.append((code, width))
        if code in (256, 257):
            return
        emitted += 1
        if 258 + emitted - 1 + 1 >= (1 << width) and width < 12:
            width += 1

    table = {bytes([i]): i for i in range(256)}
    nxt, word = 258, b""
    emit(256)
    for byte in data:
        candidate = word + bytes([byte])
        if candidate in table:
            word = candidate
            continue
        emit(table[word])
        table[candidate], nxt = nxt, nxt + 1
        word = bytes([byte])
    if word:
        emit(table[word])
    emit(257)
    value, nbits = 0, 0
    for code, w in codes:
        value, nbits = (value << w) | code, nbits + w
    pad = -nbits % 8
    return (value << pad).to_bytes((nbits + pad) // 8, "big")


class LzwTests(unittest.TestCase):
    def test_roundtrip_short(self):
        data = b"TOBEORNOTTOBEORTOBEORNOT"
        self.assertEqual(ingest_chirps.lzw_decode(_lzw_encode(data)), data)

    def test_roundtrip_crosses_code_width_and_kwkwk(self):
        rng = random.Random(7)
        data = bytes(rng.choice(b"abc\x00\xff") for _ in range(3000)) + b"a" * 200
        self.assertEqual(ingest_chirps.lzw_decode(_lzw_encode(data)), data)

    def test_invalid_code_raises(self):
        # clear, "a" y luego 400, un código que todavía no está en la tabla (9 bits cada uno)
        bits = (((256 << 9) | 97) << 9) | 400
        with self.assertRaises(ValueError):
            ingest_chirps.lzw_decode((bits << 5).to_bytes(4, "big"))


class ChirpsGridTests(unittest.TestCase):
    SCALE = 0.0500000007  # float32 de 0,05, como en los GeoTIFF de CHIRPS v3

    def test_corner_point_takes_2x2_cells(self):
        tags = {33550: (self.SCALE, self.SCALE, 0.0), 33922: (0, 0, 0, -120.0, 35.0, 0)}
        self.assertEqual(ingest_chirps.point_cells(tags), ([488, 489], [689, 690]))

    def test_point_inside_a_cell_takes_one(self):
        tags = {33550: (self.SCALE, self.SCALE, 0.0), 33922: (0, 0, 0, -120.025, 35.025, 0)}
        self.assertEqual(ingest_chirps.point_cells(tags), ([489], [690]))

    def test_months_between_crosses_year(self):
        self.assertEqual(ingest_chirps.months_between("2024-11", "2025-02"),
                         [(2024, 11), (2024, 12), (2025, 1), (2025, 2)])


class RainBiasTests(unittest.TestCase):
    def _series(self):
        power = {(2020, m): (10.0, 0) for m in range(1, 13)}
        power.update({(2021, m): (20.0, 0) for m in range(1, 13)})
        power[(2021, 5)] = (20.0, 2)  # días sin dato: año incompleto
        chirps = {(y, m): 20.0 for y in (2020, 2021) for m in range(1, 13)}
        return power, chirps

    def test_annual_table_skips_incomplete_years(self):
        rows = rain_bias.annual_table(*self._series(), range(2020, 2022))
        self.assertEqual(rows[0], {"year": 2020, "power_mm": 120.0, "chirps_mm": 240.0, "power_over_chirps": 0.5})
        self.assertIsNone(rows[1]["power_mm"])
        self.assertIsNone(rows[1]["power_over_chirps"])

    def test_summary_uses_only_complete_pairs(self):
        rows = rain_bias.annual_table(*self._series(), range(2020, 2022))
        result = rain_bias.summary(rows)
        self.assertEqual(result["n_years"], 1)
        self.assertEqual(result["power_vs_chirps_pct"], -50.0)

    def test_monthly_climatology_ignores_months_with_gaps(self):
        clim = rain_bias.monthly_climatology(*self._series(), range(2020, 2022))
        self.assertEqual(clim[4], {"month": 5, "power_mm": 10.0, "chirps_mm": 20.0})
        self.assertEqual(clim[0]["power_mm"], 15.0)

    @unittest.skipUnless(ingest_chirps.OUTPUT.exists(), "falta la serie CHIRPS procesada")
    def test_processed_chirps_series_is_complete(self):
        months = rain_bias.chirps_monthly()
        self.assertTrue(all(months.get((y, m)) is not None for y in range(1981, 2026) for m in range(1, 13)))


class BacktestRowTests(unittest.TestCase):
    def _row(self, **changes):
        values = dict(target=2015, k=5, rotation_id="rice_melon", metric="deficit_mm", truth=100.0,
                      analog_years=(1997, 1987), p10=90.0, p50=120.0, p90=130.0,
                      clim_p10=50.0, clim_p50=60.0, clim_p90=95.0, n_clim=31)
        values.update(changes)
        return backtest.Row(**values)

    def test_inside_and_errors(self):
        row = self._row()
        self.assertTrue(row.inside)
        self.assertFalse(row.clim_inside)
        self.assertEqual(row.abs_error, 20.0)
        self.assertEqual(row.clim_abs_error, 40.0)

    def test_null_truth_gives_null_results(self):
        row = self._row(truth=None)
        self.assertIsNone(row.inside)
        self.assertIsNone(row.abs_error)
        self.assertIsNone(row.clim_inside)

    def test_irrigation_only_counts_for_rice_melon(self):
        self.assertTrue(backtest._relevant(self._row(metric="irrigation_requirement_mm")))
        self.assertFalse(backtest._relevant(self._row(rotation_id="rice_legume",
                                                      metric="irrigation_requirement_mm")))
        self.assertTrue(backtest._relevant(self._row(rotation_id="rice_legume")))


if __name__ == "__main__":
    unittest.main()
