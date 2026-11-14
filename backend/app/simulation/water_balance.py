"""Balance hídrico diario del cultivo — FAO-56 capítulo 8.

Modelo de agotamiento radicular (Eq. 85)::

    Dr_i = Dr_{i-1} − (P − RO)_i − I_i + ETa_i + DP_i        con 0 ≤ Dr_i ≤ TAW

con TAW (Eq. 82), RAW (Eq. 83), Ks (Eq. 84), Kc diario por etapas (Eq. 66) y
las decisiones D1–D6 del proyecto. Unidades: mm y mm/día; Zr en m; θ en m3/m3.

Supuestos explícitos (ver ``df.attrs["warnings"]``):
- Escorrentía por umbral: RO = runoff_fraction·max(0, P − runoff_threshold_mm).
- DP = exceso de agua cuando Dr quedaría < 0 (Eq. 88 simplificada).
- Riego "refill_at_raw": si Dr ≥ RAW al inicio del día, I = Dr.
- Barbecho: kc_fallow, Zr = 0.15 m, p = 0.5.
- Zr constante por ciclo (P0): el crecimiento radicular es P1.
- Régimen inundado simplificado: Dr = 0 y demanda = ETc + percolación.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

import numpy as np
import pandas as pd

from app.simulation.contract import (
    CropLibrary,
    CropParameters,
    ModelAssumptions,
    RotationSchedule,
    SoilProfile,
)

#: Profundidad radicular usada en barbecho [m] (D5).
FALLOW_ROOT_DEPTH_M = 0.15
#: Fracción de agotamiento sin estrés en barbecho [-] (D5).
FALLOW_P_DEPLETION = 0.5
#: Columnas de salida del balance diario.
BALANCE_COLUMNS = [
    "date",
    "crop_id",
    "stage",
    "kc",
    "et0_mm",
    "etc_mm",
    "eta_mm",
    "rain_mm",
    "runoff_mm",
    "irrigation_mm",
    "deep_perc_mm",
    "depletion_mm",
    "taw_mm",
    "raw_mm",
    "ks",
]


@dataclass(frozen=True)
class CropCycle:
    """Cultivo materializado con fechas absolutas dentro de una temporada."""

    crop_id: str
    params: CropParameters
    sowing: date
    end: date
    irrigated: bool
    regime: Literal["upland", "flooded"]

    @property
    def stage_days(self) -> list[int]:
        if self.params.stage_days is None:
            raise ValueError(f"'{self.crop_id}' no tiene stage_days; no se puede simular.")
        return self.params.stage_days

    @property
    def p_depletion(self) -> float:
        if self.params.p_depletion is None:
            raise ValueError(f"'{self.crop_id}' no tiene p_depletion; no se puede simular.")
        return self.params.p_depletion

    @property
    def root_depth_m(self) -> float:
        if self.params.root_depth_max_m is None:
            raise ValueError(
                f"'{self.crop_id}' no tiene root_depth_max_m; no se puede simular."
            )
        return self.params.root_depth_max_m

    def day_index(self, day: date) -> int:
        """Índice 0-based dentro del ciclo (0 = día de siembra)."""
        return (day - self.sowing).days


def resolve_season_date(mmdd: str, season_year: int, season_start_mmdd: str = "05-01") -> date:
    """Resuelve un ``MM-DD`` dentro de la temporada agrícola (D6).

    La temporada N va del 1 de mayo N al 30 de abril N+1: los meses anteriores
    al inicio de temporada caen en el año N+1.
    """
    month, day = (int(part) for part in mmdd.split("-"))
    start_month = int(season_start_mmdd.split("-")[0])
    year = season_year if month >= start_month else season_year + 1
    return date(year, month, day)


def build_cycles(
    rotation: RotationSchedule,
    crops: CropLibrary | dict[str, CropParameters],
    season_year: int,
    assumptions: ModelAssumptions | None = None,
) -> tuple[list[CropCycle], list[str]]:
    """Convierte una rotación (fechas MM-DD) en ciclos con fechas absolutas.

    Recorta el ciclo si excede el fin de temporada (30 abr) con warning.
    """
    assumptions = assumptions or ModelAssumptions()
    catalog = crops.crops if isinstance(crops, CropLibrary) else crops
    season_end = date(season_year + 1, 4, 30)
    warnings: list[str] = []
    cycles: list[CropCycle] = []

    for segment in rotation.segments:
        if segment.crop_id not in catalog:
            raise KeyError(f"Cultivo '{segment.crop_id}' no está en el catálogo YAML.")
        params = catalog[segment.crop_id]
        if params.stage_days is None:
            raise ValueError(
                f"'{segment.crop_id}' no tiene stage_days (¿sin fuente FAO?); "
                "no se puede simular."
            )
        sowing = resolve_season_date(
            segment.sowing_mmdd, season_year, assumptions.season_start_mmdd
        )
        end = sowing + timedelta(days=sum(params.stage_days) - 1)
        if end > season_end:
            warnings.append(
                f"Ciclo de '{segment.crop_id}' recortado al fin de temporada "
                f"({end} > {season_end})."
            )
            end = season_end
        cycles.append(
            CropCycle(
                crop_id=segment.crop_id,
                params=params,
                sowing=sowing,
                end=end,
                irrigated=segment.irrigated,
                regime=segment.regime or "upland",
            )
        )
    return sorted(cycles, key=lambda cycle: cycle.sowing), warnings


def daily_kc(cycle: CropCycle | None, kc_fallow: float, day: date) -> tuple[float, str]:
    """Kc del día por etapas con interpolación lineal (Eq. 66, Fig. 25).

    En desarrollo: ``Kc = Kc_ini + (d − L_ini)/L_dev · (Kc_mid − Kc_ini)``.
    En maduración: ``Kc = Kc_mid + (d − L_ini − L_dev − L_mid)/L_late · (Kc_end − Kc_mid)``.
    """
    if cycle is None:
        return kc_fallow, "fallow"
    params = cycle.params
    for value in (params.kc_ini, params.kc_mid, params.kc_end):
        if value is None:
            raise ValueError(
                f"'{cycle.crop_id}' tiene Kc incompleto (null); no se puede simular."
            )
    l_ini, l_dev, l_mid, l_late = cycle.stage_days
    index = cycle.day_index(day)
    if index < l_ini:
        return float(params.kc_ini), "ini"
    if index < l_ini + l_dev:
        fraction = (index - l_ini) / l_dev
        kc = params.kc_ini + fraction * (params.kc_mid - params.kc_ini)
        return float(kc), "dev"
    if index < l_ini + l_dev + l_mid:
        return float(params.kc_mid), "mid"
    fraction = (index - (l_ini + l_dev + l_mid)) / l_late
    kc = params.kc_mid + fraction * (params.kc_end - params.kc_mid)
    return float(kc), "late"


def total_available_water(theta_fc: float, theta_wp: float, root_depth_m: float) -> float:
    """TAW = 1000·(θfc − θwp)·Zr [mm] — Eq. 82."""
    return 1000.0 * (theta_fc - theta_wp) * root_depth_m


def readily_available_water(taw_mm: float, p_depletion: float) -> float:
    """RAW = p·TAW [mm] — Eq. 83."""
    return p_depletion * taw_mm


def stress_coefficient(dr_mm: float, taw_mm: float, p_depletion: float) -> float:
    """Ks = 1 si Dr ≤ RAW; si no ``(TAW − Dr)/((1 − p)·TAW)`` — Eq. 84."""
    raw = readily_available_water(taw_mm, p_depletion)
    if dr_mm <= raw:
        return 1.0
    denominator = (1.0 - p_depletion) * taw_mm
    if denominator <= 0:
        return 0.0
    return float(np.clip((taw_mm - dr_mm) / denominator, 0.0, 1.0))


def runoff_mm(rain_mm: float, threshold_mm: float, fraction: float) -> float:
    """RO = fraction·max(0, P − umbral) [mm] (D3, escorrentía simplificada)."""
    return fraction * max(0.0, rain_mm - threshold_mm)


def _active_cycle(cycles: list[CropCycle], day: date) -> CropCycle | None:
    for cycle in cycles:
        if cycle.sowing <= day <= cycle.end:
            return cycle
    return None


def simulate_water_balance(
    climate: pd.DataFrame,
    soil: SoilProfile,
    rotation: RotationSchedule,
    crops: CropLibrary | dict[str, CropParameters],
    assumptions: ModelAssumptions | None = None,
    mode: Literal["rainfed", "managed"] = "rainfed",
) -> pd.DataFrame:
    """Balance hídrico diario (Eq. 85) para una rotación y una temporada.

    ``climate`` debe traer ``date``, ``rain_mm`` y ``et0_mm`` (ET0 calculada con
    :func:`app.simulation.et0.et0_pm`). Devuelve un DataFrame con
    :data:`BALANCE_COLUMNS` y las advertencias en ``df.attrs["warnings"]``.

    Modos (D1): ``rainfed`` no aplica riego en ningún segmento; ``managed``
    aplica ``refill_at_raw`` solo en segmentos con ``irrigated=True``.
    """
    if mode not in ("rainfed", "managed"):
        raise ValueError(f"mode inválido: {mode!r} (usar 'rainfed' o 'managed')")
    assumptions = assumptions or ModelAssumptions()

    missing = [col for col in ("date", "rain_mm", "et0_mm") if col not in climate.columns]
    if missing:
        raise ValueError("Falta(n) columna(s) en climate: " + ", ".join(missing))

    frame = climate.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date").reset_index(drop=True)
    if frame.empty:
        raise ValueError("La serie climática está vacía.")

    start_month = int(assumptions.season_start_mmdd.split("-")[0])
    first_day = frame["date"].iloc[0]
    season_year = first_day.year if first_day.month >= start_month else first_day.year - 1

    cycles, warnings = build_cycles(rotation, crops, season_year, assumptions)

    rows: list[dict[str, object]] = []
    dr: float | None = None
    current_taw: float | None = None
    flooded_warned = False

    for record in frame.itertuples(index=False):
        day: date = record.date.date()
        cycle = _active_cycle(cycles, day)

        if cycle is None:
            root_depth = FALLOW_ROOT_DEPTH_M
            p_depletion = FALLOW_P_DEPLETION
            kc, stage = daily_kc(None, assumptions.kc_fallow, day)
            regime = "upland"
            irrigated = False
        else:
            root_depth = cycle.root_depth_m
            p_depletion = cycle.p_depletion
            kc, stage = daily_kc(cycle, assumptions.kc_fallow, day)
            regime = cycle.regime
            irrigated = cycle.irrigated and mode == "managed"

        taw = total_available_water(soil.theta_fc, soil.theta_wp, root_depth)
        raw = readily_available_water(taw, p_depletion)

        if dr is None:
            dr = assumptions.initial_depletion_fraction * taw
            warnings.append(
                f"Dr inicial = {dr:.2f} mm "
                f"({assumptions.initial_depletion_fraction:.2f}·TAW), {day}."
            )
        elif current_taw is not None and not np.isclose(taw, current_taw):
            previous = dr
            dr = dr * taw / current_taw
            warnings.append(
                f"Dr reescalado de {previous:.2f} a {dr:.2f} mm el {day} "
                f"por cambio de Zr (TAW {current_taw:.1f} → {taw:.1f} mm)."
            )
        current_taw = taw
        dr = float(np.clip(dr, 0.0, taw))

        et0 = float(record.et0_mm)
        rain = float(record.rain_mm)
        ro = runoff_mm(rain, assumptions.runoff_threshold_mm, assumptions.runoff_fraction)
        infiltration = rain - ro
        etc = kc * et0

        if regime == "flooded":
            if mode != "managed":
                raise ValueError(
                    "El régimen 'flooded' exige mode='managed' (el arroz inundado "
                    "no es un cultivo de secano; D2)."
                )
            demand = etc + assumptions.flooded_percolation_mm_day
            irrigation = max(0.0, demand - infiltration)
            ks = 1.0
            eta = etc
            deep_perc = max(0.0, infiltration + irrigation - demand)
            dr = 0.0
            if not flooded_warned:
                warnings.append(
                    "régimen inundado simplificado: Dr = 0, demanda = "
                    f"ETc + {assumptions.flooded_percolation_mm_day:g} mm/día "
                    f"(percolación, verified: false)."
                )
                flooded_warned = True
        else:
            ks = stress_coefficient(dr, taw, p_depletion)
            eta = ks * etc
            irrigation = dr if (irrigated and dr >= raw) else 0.0
            available = infiltration + irrigation
            # El agotamiento no puede pasar de TAW: se limita ETa al agua restante.
            eta = min(eta, max(0.0, taw - dr + available))
            expected = dr - available + eta
            deep_perc = max(0.0, -expected)
            dr = float(np.clip(expected, 0.0, taw))

        rows.append(
            {
                "date": day,
                "crop_id": cycle.crop_id if cycle else None,
                "stage": stage,
                "kc": kc,
                "et0_mm": et0,
                "etc_mm": etc,
                "eta_mm": eta,
                "rain_mm": rain,
                "runoff_mm": ro,
                "irrigation_mm": irrigation,
                "deep_perc_mm": deep_perc,
                "depletion_mm": dr,
                "taw_mm": taw,
                "raw_mm": raw,
                "ks": ks,
            }
        )

    result = pd.DataFrame(rows, columns=BALANCE_COLUMNS)
    result.attrs["warnings"] = warnings
    return result
