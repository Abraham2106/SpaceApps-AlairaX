"""Tests del balance hídrico diario (FAO-56 cap. 8) — los más importantes del proyecto."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.simulation.contract import (
    CropParameters,
    CropSegment,
    ModelAssumptions,
    RotationSchedule,
    SoilProfile,
    from_power_csv,
)
from app.simulation.et0 import et0_pm
from app.simulation.parameters import load_crops, load_rotations
from app.simulation.water_balance import (
    BALANCE_COLUMNS,
    daily_kc,
    resolve_season_date,
    simulate_water_balance,
    stress_coefficient,
    total_available_water,
)

PARAMS = Path(__file__).resolve().parents[2] / "research" / "parameters"
POWER_CSV = (
    Path(__file__).resolve().parents[2]
    / "datasets"
    / "examples"
    / "power_liberia_urbano_2015_2025.csv"
)

#: Suelo de prueba: TAW = 1000·(0.30−0.10)·1 m = 200 mm.
SOIL = SoilProfile(theta_fc=0.30, theta_wp=0.10, source="test")


def _crop(**overrides) -> CropParameters:
    data = {
        "display_name": "Cultivo de prueba",
        "kc_ini": 1.0,
        "kc_mid": 1.0,
        "kc_end": 1.0,
        "stage_days": [365, 1, 1, 1],
        "root_depth_max_m": 1.0,
        "p_depletion": 0.5,
        "source": "test",
        "verified": False,
    }
    data.update(overrides)
    return CropParameters(**data)


def _rotation(
    crop_ids: list[str] | None = None,
    sowings: list[str] | None = None,
    irrigated: list[bool] | None = None,
    regimes: list[str | None] | None = None,
) -> RotationSchedule:
    crop_ids = crop_ids or ["c1"]
    sowings = sowings or ["05-01"]
    irrigated = irrigated or [False] * len(crop_ids)
    regimes = regimes or [None] * len(crop_ids)
    return RotationSchedule(
        rotation_id="test",
        name="Rotación de prueba",
        segments=[
            CropSegment(
                crop_id=crop_id,
                sowing_mmdd=sowing,
                irrigated=irrigated[index],
                regime=regimes[index],
            )
            for index, (crop_id, sowing) in enumerate(zip(crop_ids, sowings))
        ],
    )


def _climate(days: int, rain: list[float] | float = 0.0, et0: float = 4.0) -> pd.DataFrame:
    rains = rain if isinstance(rain, list) else [float(rain)] * days
    return pd.DataFrame(
        {
            "date": pd.date_range("2021-05-01", periods=days, freq="D"),
            "rain_mm": rains,
            "et0_mm": et0,
        }
    )


# --------------------------------------------------------------------------- #
# Un caso a mano: 5 días, Kc = 1, ET0 = 4 mm/día, TAW = 200 mm, RAW = 100 mm
# --------------------------------------------------------------------------- #


def test_hand_calculated_five_days() -> None:
    """Números calculados a mano con Eq. 84 y Eq. 85 (ver comentarios por día)."""
    climate = _climate(5, rain=[0.0, 0.0, 0.0, 50.0, 0.0], et0=4.0)
    rotation = _rotation()
    result = simulate_water_balance(
        climate, SOIL, rotation, {"c1": _crop(stage_days=[5, 1, 1, 1])}
    )

    # Dr0 = 0.5·200 = 100 mm
    # Día 1: Dr=100=RAW → Ks=1, ETa=4        → Dr=104
    # Día 2: Ks=(200−104)/100=0.96, ETa=3.84 → Dr=107.84
    # Día 3: Ks=(200−107.84)/100=0.9216      → ETa=3.6864 → Dr=111.5264
    # Día 4: lluvia 50 (RO=0); Ks=0.884736   → ETa=3.538944 → Dr=65.065344
    # Día 5: Dr<RAW → Ks=1, ETa=4            → Dr=69.065344
    expected_dr = [104.0, 107.84, 111.5264, 65.065344, 69.065344]
    expected_eta = [4.0, 3.84, 3.6864, 3.538944, 4.0]
    expected_ks = [1.0, 0.96, 0.9216, 0.884736, 1.0]

    np.testing.assert_allclose(result["depletion_mm"], expected_dr, atol=1e-9, rtol=0)
    np.testing.assert_allclose(result["eta_mm"], expected_eta, atol=1e-9, rtol=0)
    np.testing.assert_allclose(result["ks"], expected_ks, atol=1e-12, rtol=0)
    assert (result["irrigation_mm"] == 0).all()
    assert (result["deep_perc_mm"] == 0).all()


# --------------------------------------------------------------------------- #
# Balance de masa
# --------------------------------------------------------------------------- #


def test_mass_balance_rainfed() -> None:
    rng = np.random.default_rng(2026)
    days = 60
    rain = (rng.random(days) < 0.25) * rng.uniform(0, 80, days)
    climate = _climate(days, rain=rain.tolist(), et0=4.5)
    result = simulate_water_balance(
        climate, SOIL, _rotation(), {"c1": _crop(stage_days=[60, 1, 1, 1])}
    )

    dr_initial = 0.5 * 200.0
    inflows = (result["rain_mm"] - result["runoff_mm"] + result["irrigation_mm"]).sum()
    outflows = (result["eta_mm"] + result["deep_perc_mm"]).sum()
    assert result["depletion_mm"].iloc[-1] - dr_initial == pytest.approx(
        outflows - inflows, abs=1e-9
    )


def test_depletion_bounds_and_flux_limits() -> None:
    rng = np.random.default_rng(7)
    days = 90
    rain = (rng.random(days) < 0.3) * rng.uniform(0, 120, days)
    result = simulate_water_balance(
        _climate(days, rain=rain.tolist(), et0=5.0),
        SOIL,
        _rotation(),
        {"c1": _crop(stage_days=[90, 1, 1, 1])},
    )

    assert (result["depletion_mm"] >= 0).all()
    assert (result["depletion_mm"] <= result["taw_mm"] + 1e-9).all()
    assert result["ks"].between(0, 1).all()
    assert (result["eta_mm"] <= result["etc_mm"] + 1e-9).all()
    assert np.allclose(result["taw_mm"], 200.0)
    assert np.allclose(result["raw_mm"], 100.0)


# --------------------------------------------------------------------------- #
# Dinámica
# --------------------------------------------------------------------------- #


def test_no_rain_no_irrigation_depletes_monotonically() -> None:
    result = simulate_water_balance(
        _climate(20, rain=0.0, et0=5.0),
        SOIL,
        _rotation(),
        {"c1": _crop(stage_days=[20, 1, 1, 1])},
    )

    assert np.all(np.diff(result["depletion_mm"].to_numpy()) > 0)
    assert result["ks"].iloc[0] == pytest.approx(1.0)
    assert result["ks"].iloc[-1] < 1.0
    # Ks no puede subir sin una entrada de agua.
    assert np.all(np.diff(result["ks"].to_numpy()) <= 1e-12)


def test_huge_rain_empties_depletion_and_splits_excess() -> None:
    result = simulate_water_balance(
        _climate(3, rain=[0.0, 200.0, 0.0], et0=4.0),
        SOIL,
        _rotation(),
        {"c1": _crop(stage_days=[3, 1, 1, 1])},
    )

    assert result["depletion_mm"].iloc[1] == pytest.approx(0.0)
    assert result["runoff_mm"].iloc[1] == pytest.approx(0.3 * (200.0 - 60.0))  # 42 mm
    # Día 1 deja Dr = 104 (ETa = 4). Día 2: infiltra 200 − 42 = 158 mm y ETa = 3.84
    # (Ks = (200 − 104)/100 = 0.96) → 104 − 158 + 3.84 = −50.16 mm de excedente.
    assert result["deep_perc_mm"].iloc[1] == pytest.approx(50.16)


def test_managed_refill_keeps_depletion_below_raw() -> None:
    result = simulate_water_balance(
        _climate(20, rain=0.0, et0=4.0),
        SOIL,
        _rotation(irrigated=[True]),
        {"c1": _crop(stage_days=[20, 1, 1, 1])},
        mode="managed",
    )

    assert (result["irrigation_mm"] > 0).any()
    # refill_at_raw: al inicio del día siguiente Dr vuelve a ~0 (solo ETa del día).
    assert (result["depletion_mm"] <= result["raw_mm"] + 1e-9).all()
    assert result["irrigation_mm"].iloc[0] == pytest.approx(100.0)


def test_fallow_between_crops_rescales_depletion() -> None:
    rotation = _rotation(
        crop_ids=["c1", "c2"], sowings=["05-01", "06-01"], irrigated=[False, False]
    )
    crops = {
        "c1": _crop(stage_days=[5, 1, 1, 1]),
        "c2": _crop(stage_days=[5, 1, 1, 1], root_depth_max_m=0.5),
    }
    result = simulate_water_balance(_climate(45, rain=0.0, et0=4.0), SOIL, rotation, crops)

    fallow = result[result["stage"] == "fallow"]
    assert not fallow.empty
    assert np.allclose(fallow["kc"], 0.15)
    assert np.allclose(fallow["taw_mm"], 1000 * 0.20 * 0.15)
    assert any("reescalado" in warning for warning in result.attrs["warnings"])
    assert (result["depletion_mm"] <= result["taw_mm"] + 1e-9).all()


def test_flooded_regime_keeps_zero_depletion_and_irrigates_demand() -> None:
    result = simulate_water_balance(
        _climate(3, rain=0.0, et0=5.0),
        SOIL,
        _rotation(irrigated=[True], regimes=["flooded"]),
        {"c1": _crop(stage_days=[3, 1, 1, 1])},
        mode="managed",
    )

    assert (result["depletion_mm"] == 0.0).all()
    # Demanda diaria = ETc (5) + percolación (4) = 9 mm, cubierta por riego.
    assert np.allclose(result["irrigation_mm"], 9.0)
    assert (result["ks"] == 1.0).all()
    assert any("inundado" in warning for warning in result.attrs["warnings"])


def test_flooded_requires_managed_mode() -> None:
    with pytest.raises(ValueError, match="flooded"):
        simulate_water_balance(
            _climate(2),
            SOIL,
            _rotation(regimes=["flooded"]),
            {"c1": _crop()},
            mode="rainfed",
        )


def test_missing_et0_column_raises() -> None:
    climate = _climate(3).drop(columns=["et0_mm"])
    with pytest.raises(ValueError, match="et0_mm"):
        simulate_water_balance(climate, SOIL, _rotation(), {"c1": _crop()})


# --------------------------------------------------------------------------- #
# Piezas sueltas
# --------------------------------------------------------------------------- #


def test_stress_coefficient_equation() -> None:
    assert stress_coefficient(0.0, 200.0, 0.5) == 1.0
    assert stress_coefficient(100.0, 200.0, 0.5) == 1.0
    assert stress_coefficient(150.0, 200.0, 0.5) == pytest.approx(0.5)
    assert stress_coefficient(200.0, 200.0, 0.5) == 0.0


def test_taw_and_raw() -> None:
    assert total_available_water(0.30, 0.10, 1.0) == pytest.approx(200.0)
    assert total_available_water(0.30, 0.10, 0.15) == pytest.approx(30.0)


def test_daily_kc_curve_is_piecewise_linear() -> None:
    cycle_params = _crop(
        kc_ini=0.3, kc_mid=1.1, kc_end=0.5, stage_days=[10, 10, 10, 10]
    )
    rotation = _rotation()
    cycles, _ = __import__(
        "app.simulation.water_balance", fromlist=["build_cycles"]
    ).build_cycles(rotation, {"c1": cycle_params}, 2021)

    cycle = cycles[0]
    assert daily_kc(cycle, 0.15, date(2021, 5, 1))[0] == pytest.approx(0.3)
    assert daily_kc(cycle, 0.15, date(2021, 5, 11))[0] == pytest.approx(0.3)
    assert daily_kc(cycle, 0.15, date(2021, 5, 16))[0] == pytest.approx(0.7)
    assert daily_kc(cycle, 0.15, date(2021, 5, 21))[0] == pytest.approx(1.1)
    assert daily_kc(cycle, 0.15, date(2021, 5, 31))[0] == pytest.approx(1.1)
    assert daily_kc(cycle, 0.15, date(2021, 6, 5))[0] == pytest.approx(0.8)
    # Último día del ciclo (índice 39): maduración 9/10 → 1.1 + 0.9·(0.5 − 1.1) = 0.56.
    assert daily_kc(cycle, 0.15, date(2021, 6, 9))[0] == pytest.approx(0.56)


def test_season_date_resolution_d6() -> None:
    assert resolve_season_date("06-01", 2021) == date(2021, 6, 1)
    assert resolve_season_date("12-01", 2021) == date(2021, 12, 1)
    assert resolve_season_date("01-15", 2021) == date(2022, 1, 15)
    assert resolve_season_date("04-30", 2021) == date(2022, 4, 30)


# --------------------------------------------------------------------------- #
# Meta del sábado: rice_melon corre sobre una temporada del fixture
# --------------------------------------------------------------------------- #


def test_rice_melon_runs_on_fixture_season() -> None:
    climate, _ = from_power_csv(POWER_CSV)
    season = climate[
        (climate["date"] >= "2015-05-01") & (climate["date"] <= "2016-04-30")
    ].reset_index(drop=True)
    assert len(season) == 366

    season["et0_mm"] = et0_pm(
        season["tmax_c"].to_numpy(),
        season["tmin_c"].to_numpy(),
        season["rh_mean_pct"].to_numpy(),
        season["wind2m_ms"].to_numpy(),
        season["rs_mj_m2_day"].to_numpy(),
        10.635,
        144.0,
        season["date"].dt.day_of_year.to_numpy(),
    )

    crops = load_crops(PARAMS / "crops.yaml")
    rotation = next(
        rot for rot in load_rotations(PARAMS / "rotations.yaml").rotations
        if rot.rotation_id == "rice_melon"
    )

    result = simulate_water_balance(
        season,
        SoilProfile.from_soilgrids(280.0, 140.0),
        rotation,
        crops,
        ModelAssumptions(),
        mode="managed",
    )

    assert list(result.columns) == BALANCE_COLUMNS
    assert len(result) == len(season)
    numeric = [col for col in BALANCE_COLUMNS if col not in ("date", "crop_id", "stage")]
    assert not result[numeric].isna().any().any()
    assert (result["depletion_mm"] >= 0).all()
    assert (result["depletion_mm"] <= result["taw_mm"] + 1e-9).all()
    assert set(result["crop_id"].dropna()) == {"rice", "melon"}
    assert (result.loc[result["crop_id"] == "melon", "irrigation_mm"] > 0).any()
    assert any("reescalado" in warning for warning in result.attrs["warnings"])
