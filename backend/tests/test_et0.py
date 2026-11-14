"""Tests de ET0 FAO-56 (Eq. 6) contra el Ejemplo 18 y la serie de Liberia."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.simulation.contract import from_power_csv
from app.simulation.et0 import (
    atmospheric_pressure,
    clear_sky_radiation,
    et0_pm,
    extraterrestrial_radiation,
    mean_saturation_vp,
    net_radiation,
    psychrometric_constant,
    saturation_vp,
    vapor_pressure_from_rhmax_rhmin,
    vapor_pressure_from_rhmean,
)

POWER_CSV = (
    Path(__file__).resolve().parents[2]
    / "datasets"
    / "examples"
    / "power_liberia_urbano_2015_2025.csv"
)

# Ejemplo 18 FAO-56: Uccle (Bruselas), 6 de julio, 50°48'N, 100 m.
EXAMPLE18 = {
    "tmax_c": 21.5,
    "tmin_c": 12.3,
    "rh_max_pct": 84.0,
    "rh_min_pct": 63.0,
    "ea_kpa": 1.409,
    "u2_ms": 2.078,
    "rs_mj_m2_day": 22.07,
    "lat_deg": 50.80,
    "elevation_m": 100.0,
    "doy": 187,
}


def test_example_18_vapour_pressure_terms() -> None:
    """Eqs. 11, 12 y 17: e°(Tmax)=2.564, e°(Tmin)=1.431, es=1.997, ea=1.409 kPa."""
    assert saturation_vp(21.5) == pytest.approx(2.564, abs=0.002)
    assert saturation_vp(12.3) == pytest.approx(1.431, abs=0.002)
    assert mean_saturation_vp(21.5, 12.3) == pytest.approx(1.997, abs=0.002)
    assert vapor_pressure_from_rhmax_rhmin(21.5, 12.3, 84.0, 63.0) == pytest.approx(
        1.409, abs=0.002
    )


def test_example_18_pressure_terms() -> None:
    """Eqs. 7 y 8: P=100.1 kPa, γ=0.0666 kPa/°C."""
    assert atmospheric_pressure(100.0) == pytest.approx(100.1, abs=0.05)
    assert psychrometric_constant(100.0) == pytest.approx(0.0666, abs=0.0002)


def test_example_18_radiation_terms() -> None:
    """Eqs. 21, 37 y 40: Ra≈41.09, Rso≈30.90, Rn≈13.28 MJ m-2 día-1."""
    ra = extraterrestrial_radiation(50.80, 187)
    assert ra == pytest.approx(41.09, abs=0.05)

    rso = clear_sky_radiation(ra, 100.0)
    assert rso == pytest.approx(30.90, abs=0.05)

    rn = net_radiation(21.5, 12.3, 1.409, 22.07, ra, 100.0)
    assert rn == pytest.approx(13.28, abs=0.05)


def test_example_18_et0_matches_fao() -> None:
    """Eq. 6: ET0 = 3.88 ≈ 3.9 mm/día (texto FAO-56).

    El ejemplo da ``ea`` por Eq. 17 (RHmax/RHmin). Como ``et0_pm`` toma RHmedia
    (Eq. 19), se usa la RHmedia equivalente que reproduce esa misma ``ea``
    (100·1.409/es); así se verifica la ecuación, no el redondeo de la tabla.
    """
    es = mean_saturation_vp(EXAMPLE18["tmax_c"], EXAMPLE18["tmin_c"])
    rh_mean_equiv = 100.0 * EXAMPLE18["ea_kpa"] / es

    assert vapor_pressure_from_rhmean(rh_mean_equiv, es) == pytest.approx(1.409, abs=1e-3)

    et0 = et0_pm(
        EXAMPLE18["tmax_c"],
        EXAMPLE18["tmin_c"],
        rh_mean_equiv,
        EXAMPLE18["u2_ms"],
        EXAMPLE18["rs_mj_m2_day"],
        EXAMPLE18["lat_deg"],
        EXAMPLE18["elevation_m"],
        EXAMPLE18["doy"],
    )
    assert et0 == pytest.approx(3.88, abs=0.1)


def test_et0_liberia_annual_mean_is_plausible() -> None:
    """Serie de Liberia (punto urbano): ET0 media diaria ≈ 4.5–6.5 mm/día."""
    climate, _ = from_power_csv(POWER_CSV)
    et0 = et0_pm(
        climate["tmax_c"].to_numpy(),
        climate["tmin_c"].to_numpy(),
        climate["rh_mean_pct"].to_numpy(),
        climate["wind2m_ms"].to_numpy(),
        climate["rs_mj_m2_day"].to_numpy(),
        lat_deg=10.635,
        elevation_m=144.0,
        doy=climate["date"].dt.day_of_year.to_numpy(),
    )

    daily_mean = float(np.nanmean(et0))
    assert 4.5 <= daily_mean <= 6.5, (
        f"ET0 media de Liberia = {daily_mean:.2f} mm/día fuera de 4.5–6.5; "
        "revisar dados/coordenadas antes de tocar el test."
    )


def test_et0_is_never_negative_and_has_no_nan() -> None:
    climate, _ = from_power_csv(POWER_CSV)
    et0 = et0_pm(
        climate["tmax_c"].to_numpy(),
        climate["tmin_c"].to_numpy(),
        climate["rh_mean_pct"].to_numpy(),
        climate["wind2m_ms"].to_numpy(),
        climate["rs_mj_m2_day"].to_numpy(),
        10.635,
        144.0,
        climate["date"].dt.day_of_year.to_numpy(),
    )

    assert np.isfinite(et0).all()
    assert (et0 >= 0).all()


def test_et0_never_negative_across_extreme_inputs() -> None:
    """Propiedad de contrato: ET0 ≥ 0 (el clip es defensivo; Rn diaria rara vez < 0)."""
    et0 = et0_pm(
        tmax_c=np.array([45.0, 10.0, 5.0, 30.0, 40.0]),
        tmin_c=np.array([35.0, 9.0, 0.0, 10.0, 5.0]),
        rh_mean_pct=np.array([5.0, 99.0, 100.0, 50.0, 90.0]),
        u2_ms=np.array([20.0, 0.01, 0.5, 2.0, 8.0]),
        rs_mj_m2_day=np.array([35.0, 0.0, 1.0, 20.0, 10.0]),
        lat_deg=10.635,
        elevation_m=144.0,
        doy=np.array([15, 180, 350, 90, 250]),
    )

    assert np.isfinite(et0).all()
    assert (et0 >= 0).all()


def test_vectorized_input_returns_array() -> None:
    dates = pd.date_range("2021-05-01", periods=3, freq="D")
    et0 = et0_pm(
        np.array([30.0, 31.0, 32.0]),
        np.array([20.0, 21.0, 22.0]),
        np.array([70.0, 65.0, 60.0]),
        np.array([2.0, 2.5, 3.0]),
        np.array([20.0, 22.0, 24.0]),
        10.635,
        144.0,
        dates.day_of_year.to_numpy(),
    )

    assert isinstance(et0, np.ndarray)
    assert et0.shape == (3,)
    assert (et0 > 0).all()
