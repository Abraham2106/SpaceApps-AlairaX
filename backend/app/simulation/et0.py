"""ET0 por FAO-56 Penman-Monteith, vectorizado con numpy.

Todas las funciones aceptan escalares o arrays (broadcasting de numpy) y usan
las unidades de FAO-56:
- ET0 [mm/día]
- radiación [MJ m-2 día-1]
- presión de vapor [kPa], presión atmosférica [kPa]
- temperatura [°C], viento a 2 m [m/s], elevación [m s.n.m.]

Ecuaciones (Allen et al., 1998, FAO Irrigation and Drainage Paper 56):
Eq. 6 (Penman-Monteith), 7 (presión), 8 (γ), 11 (e°(T)), 12 (es), 13 (Δ),
17 (ea desde RHmax/RHmin), 19 (ea desde RHmean), 21 (Ra), 23 (dr), 24 (δ),
25 (ωs), 37 (Rso), 38 (Rns), 39 (Rnl). G = 0 para paso diario (Eq. 42).
https://www.fao.org/3/x0490e/x0490e00.htm
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date as _date

import numpy as np

#: Constante solar [MJ m-2 min-1] (FAO-56, cap. 3).
SOLAR_CONSTANT = 0.0820
#: Constante de Stefan-Boltzmann [MJ m-2 día-1 K-4] (Eq. 39).
STEFAN_BOLTZMANN = 4.903e-9
#: Albedo de la superficie de referencia (pasto) [-] (Eq. 38).
ALBEDO = 0.23


def _as_array(value: float | np.ndarray) -> np.ndarray:
    return np.asarray(value, dtype=float)


def _out(value: np.ndarray) -> float | np.ndarray:
    array = np.asarray(value, dtype=float)
    return float(array) if array.ndim == 0 else array


def saturation_vp(t_c: float | np.ndarray) -> float | np.ndarray:
    """Presión de vapor de saturación e°(T) [kPa] — Eq. 11."""
    t = _as_array(t_c)
    return _out(0.6108 * np.exp(17.27 * t / (t + 237.3)))


def mean_saturation_vp(
    tmax_c: float | np.ndarray, tmin_c: float | np.ndarray
) -> float | np.ndarray:
    """es = [e°(Tmax) + e°(Tmin)] / 2 [kPa] — Eq. 12."""
    return _out((_as_array(saturation_vp(tmax_c)) + _as_array(saturation_vp(tmin_c))) / 2.0)


def vapor_pressure_from_rhmean(
    rh_mean_pct: float | np.ndarray, es_kpa: float | np.ndarray
) -> float | np.ndarray:
    """ea = es · RHmean/100 [kPa] — Eq. 19 (menos recomendada por no linealidad)."""
    return _out(_as_array(es_kpa) * _as_array(rh_mean_pct) / 100.0)


def vapor_pressure_from_rhmax_rhmin(
    tmax_c: float | np.ndarray,
    tmin_c: float | np.ndarray,
    rh_max_pct: float | np.ndarray,
    rh_min_pct: float | np.ndarray,
) -> float | np.ndarray:
    """ea = [e°(Tmin)·RHmax/100 + e°(Tmax)·RHmin/100] / 2 [kPa] — Eq. 17."""
    ea = (
        _as_array(saturation_vp(tmin_c)) * _as_array(rh_max_pct) / 100.0
        + _as_array(saturation_vp(tmax_c)) * _as_array(rh_min_pct) / 100.0
    ) / 2.0
    return _out(ea)


def slope_vapor_pressure_curve(tmean_c: float | np.ndarray) -> float | np.ndarray:
    """Δ = 4098 · e°(T) / (T + 237.3)^2 [kPa/°C] — Eq. 13."""
    t = _as_array(tmean_c)
    return _out(4098.0 * _as_array(saturation_vp(t)) / (t + 237.3) ** 2)


def atmospheric_pressure(elevation_m: float | np.ndarray) -> float | np.ndarray:
    """P = 101.3 · [(293 − 0.0065 z) / 293]^5.26 [kPa] — Eq. 7."""
    z = _as_array(elevation_m)
    return _out(101.3 * ((293.0 - 0.0065 * z) / 293.0) ** 5.26)


def psychrometric_constant(elevation_m: float | np.ndarray) -> float | np.ndarray:
    """γ = 0.000665 · P [kPa/°C] — Eq. 8."""
    return _out(0.000665 * _as_array(atmospheric_pressure(elevation_m)))


def extraterrestrial_radiation(
    lat_deg: float | np.ndarray, doy: float | np.ndarray
) -> float | np.ndarray:
    """Radiación extraterrestre Ra [MJ m-2 día-1] — Eq. 21.

    ``lat_deg`` en grados decimales (positivo al norte); ``doy`` es el día
    juliano (1–365/366).
    """
    lat = np.deg2rad(_as_array(lat_deg))
    day = _as_array(doy)
    dr = 1.0 + 0.033 * np.cos(2.0 * np.pi * day / 365.0)  # Eq. 23
    declination = 0.409 * np.sin(2.0 * np.pi * day / 365.0 - 1.39)  # Eq. 24
    sunset_angle = np.arccos(np.clip(-np.tan(lat) * np.tan(declination), -1.0, 1.0))  # Eq. 25
    ra = (
        (24.0 * 60.0 / np.pi)
        * SOLAR_CONSTANT
        * dr
        * (
            sunset_angle * np.sin(lat) * np.sin(declination)
            + np.cos(lat) * np.cos(declination) * np.sin(sunset_angle)
        )
    )
    return _out(np.maximum(ra, 0.0))


def clear_sky_radiation(
    ra_mj_m2_day: float | np.ndarray, elevation_m: float | np.ndarray
) -> float | np.ndarray:
    """Rso = (0.75 + 2·10^-5 · z) · Ra [MJ m-2 día-1] — Eq. 37."""
    ra = _as_array(ra_mj_m2_day)
    z = _as_array(elevation_m)
    return _out(np.maximum((0.75 + 2e-5 * z) * ra, 1e-6))


def net_shortwave_radiation(rs_mj_m2_day: float | np.ndarray) -> float | np.ndarray:
    """Rns = (1 − α) · Rs con α = 0.23 [MJ m-2 día-1] — Eq. 38."""
    return _out((1.0 - ALBEDO) * _as_array(rs_mj_m2_day))


def net_longwave_radiation(
    tmax_c: float | np.ndarray,
    tmin_c: float | np.ndarray,
    ea_kpa: float | np.ndarray,
    rs_mj_m2_day: float | np.ndarray,
    rso_mj_m2_day: float | np.ndarray,
) -> float | np.ndarray:
    """Rnl [MJ m-2 día-1] — Eq. 39.

    ``Rnl = σ·[(Tmax,K^4 + Tmin,K^4)/2]·(0.34 − 0.14·√ea)·(1.35·Rs/Rso − 0.35)``.
    La relación de nubosidad ``Rs/Rso`` se acota a [0, 1] como pide el contrato.
    """
    tmax_k = _as_array(tmax_c) + 273.16
    tmin_k = _as_array(tmin_c) + 273.16
    ea = _as_array(ea_kpa)
    cloud_ratio = np.clip(
        _as_array(rs_mj_m2_day) / _as_array(rso_mj_m2_day), 0.0, 1.0
    )
    rnl = (
        STEFAN_BOLTZMANN
        * ((tmax_k**4 + tmin_k**4) / 2.0)
        * (0.34 - 0.14 * np.sqrt(np.maximum(ea, 0.0)))
        * (1.35 * cloud_ratio - 0.35)
    )
    return _out(rnl)


def net_radiation(
    tmax_c: float | np.ndarray,
    tmin_c: float | np.ndarray,
    ea_kpa: float | np.ndarray,
    rs_mj_m2_day: float | np.ndarray,
    ra_mj_m2_day: float | np.ndarray,
    elevation_m: float | np.ndarray,
) -> float | np.ndarray:
    """Rn = Rns − Rnl [MJ m-2 día-1] — Eq. 40."""
    rso = clear_sky_radiation(ra_mj_m2_day, elevation_m)
    rnl = net_longwave_radiation(tmax_c, tmin_c, ea_kpa, rs_mj_m2_day, rso)
    return _out(_as_array(net_shortwave_radiation(rs_mj_m2_day)) - _as_array(rnl))


def et0_pm(
    tmax_c: float | np.ndarray,
    tmin_c: float | np.ndarray,
    rh_mean_pct: float | np.ndarray,
    u2_ms: float | np.ndarray,
    rs_mj_m2_day: float | np.ndarray,
    lat_deg: float | np.ndarray,
    elevation_m: float | np.ndarray,
    doy: float | np.ndarray,
) -> float | np.ndarray:
    """ET0 diaria [mm/día] — Eq. 6, con G = 0 (Eq. 42).

    ``ET0 = [0.408·Δ·(Rn − G) + γ·(900/(T+273))·u2·(es − ea)] / [Δ + γ·(1 + 0.34·u2)]``

    Con ``rh_mean_pct`` se obtiene ``ea`` por Eq. 19. El resultado se acota a
    ``ET0 ≥ 0``; no se fuerza ningún otro límite. Si las entradas no traen
    faltantes, la salida no tiene NaN.
    """
    tmax = _as_array(tmax_c)
    tmin = _as_array(tmin_c)
    u2 = _as_array(u2_ms)
    tmean = (tmax + tmin) / 2.0

    es = _as_array(mean_saturation_vp(tmax, tmin))
    ea = _as_array(vapor_pressure_from_rhmean(rh_mean_pct, es))
    delta = _as_array(slope_vapor_pressure_curve(tmean))
    gamma = _as_array(psychrometric_constant(elevation_m))
    ra = _as_array(extraterrestrial_radiation(lat_deg, doy))
    rn = _as_array(
        net_radiation(tmax, tmin, ea, rs_mj_m2_day, ra, elevation_m)
    )
    g = 0.0  # Eq. 42: G despreciable en paso diario

    numerator = 0.408 * delta * (rn - g) + gamma * (900.0 / (tmean + 273.0)) * u2 * (es - ea)
    denominator = delta + gamma * (1.0 + 0.34 * u2)
    return _out(np.maximum(numerator / denominator, 0.0))


ET0_INPUT_FIELDS = (
    "tmax_c",
    "tmin_c",
    "relative_humidity_pct",
    "wind_speed_2m_m_s",
    "solar_radiation_mj_m2_day",
)


def et0_for_days(
    days: Sequence[Mapping[str, object]],
    lat_deg: float,
    elevation_m: float,
) -> list[float | None]:
    """ET0 FAO-56 PM para filas con los nombres del contrato ``ClimateDay``.

    Cada fila trae ``date`` (``datetime.date`` o ISO ``YYYY-MM-DD``) y las
    variables de ``ET0_INPUT_FIELDS``. Un día con cualquier variable nula
    devuelve ``None``: no se rellena ni se sustituye por cero.
    """
    out: list[float | None] = []
    for row in days:
        values = [row.get(name) for name in ET0_INPUT_FIELDS]
        if any(value is None for value in values):
            out.append(None)
            continue
        day = row["date"]
        if isinstance(day, str):
            day = _date.fromisoformat(day)
        tmax, tmin, rh, u2, rs = (float(value) for value in values)
        out.append(
            float(et0_pm(tmax, tmin, rh, u2, rs, lat_deg, elevation_m, day.timetuple().tm_yday))
        )
    return out
