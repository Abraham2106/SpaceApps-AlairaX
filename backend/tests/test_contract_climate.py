"""Tests de validación de la serie climática (contrato Fase 1)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.app.simulation.contract import ClimateDaily, from_power_csv, validate_climate

EXAMPLES = Path(__file__).resolve().parents[2] / "datasets" / "examples"
POWER_CSV = EXAMPLES / "power_liberia_urbano_2015_2025.csv"


def _frame(days: int = 10) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2021-05-01", periods=days, freq="D"),
            "rain_mm": 1.0,
            "tmax_c": 30.0,
            "tmin_c": 20.0,
            "rh_mean_pct": 70.0,
            "wind2m_ms": 2.0,
            "rs_mj_m2_day": 20.0,
        }
    )


def test_short_gaps_are_filled_with_warnings() -> None:
    frame = _frame()
    frame.loc[3:4, "tmax_c"] = np.nan  # hueco de 2 días
    frame.loc[6, "rain_mm"] = np.nan  # hueco de 1 día en lluvia

    clean, warnings = validate_climate(frame)

    assert not clean.isna().any().any()
    assert clean.loc[3, "tmax_c"] == pytest.approx(30.0)
    assert clean.loc[6, "rain_mm"] == pytest.approx(0.0)
    assert any("tmax_c" in w and "2 día" in w for w in warnings)
    assert any("rain_mm" in w and "lluvia 0" in w for w in warnings)


def test_gap_longer_than_three_days_raises() -> None:
    frame = _frame()
    frame.loc[2:5, "rh_mean_pct"] = np.nan  # 4 días seguidos

    with pytest.raises(ValueError, match="Hueco de 4 días"):
        validate_climate(frame)


def test_missing_column_raises() -> None:
    frame = _frame().drop(columns=["wind2m_ms"])

    with pytest.raises(ValueError, match="wind2m_ms"):
        validate_climate(frame)


def test_sentinel_and_plausible_ranges() -> None:
    frame = _frame()
    frame.loc[2, "tmax_c"] = -999
    frame.loc[5, "tmax_c"] = 60.0

    clean, warnings = validate_climate(frame)

    assert not clean["tmax_c"].isna().any()  # -999 se interpola
    assert clean.loc[5, "tmax_c"] == pytest.approx(60.0)  # no se descarta
    assert any("tmax_c fuera del rango plausible" in w for w in warnings)
    assert any("2021-05-06" in w for w in warnings)


def test_radiation_in_kwh_is_converted() -> None:
    frame = _frame()
    frame["rs_mj_m2_day"] = 5.0  # kWh m-2 día-1

    clean, warnings = validate_climate(frame)

    assert clean["rs_mj_m2_day"].iloc[0] == pytest.approx(18.0)
    assert any("kWh" in w and "3.6" in w for w in warnings)


def test_tmin_above_tmax_warns() -> None:
    frame = _frame()
    frame.loc[1, "tmin_c"] = 31.0

    _, warnings = validate_climate(frame)

    assert any("tmin_c > tmax_c" in w for w in warnings)


def test_from_power_csv_maps_and_drops_columns() -> None:
    clean, warnings = from_power_csv(POWER_CSV)

    assert set(ClimateDaily.COLUMNS).issubset(clean.columns)
    assert "EVPTRNS" not in clean.columns
    assert "GWETROOT" not in clean.columns
    assert len(clean) > 3000
    assert clean["date"].is_monotonic_increasing
    assert not any("kWh" in w for w in warnings)
    assert clean["tmax_c"].between(10, 45).all()


def test_power_style_yyyymmdd_dates_are_parsed() -> None:
    raw = pd.DataFrame(
        {
            "fecha": [20210501, 20210502],
            "PRECTOTCORR": [0.0, 12.5],
            "T2M_MAX": [31.0, 30.0],
            "T2M_MIN": [22.0, 21.0],
            "RH2M": [75.0, 80.0],
            "WS2M": [2.0, 2.5],
            "ALLSKY_SFC_SW_DWN": [19.0, 20.0],
            "EVPTRNS": [4.5, 4.7],
            "GWETROOT": [0.6, 0.6],
        }
    )
    tmp = EXAMPLES / "_tmp_power.csv"
    try:
        raw.to_csv(tmp, index=False)
        clean, _ = from_power_csv(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    assert clean["date"].tolist() == [pd.Timestamp("2021-05-01"), pd.Timestamp("2021-05-02")]
