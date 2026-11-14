"""Kernel FAO-56 sobre el contrato M1 de Abe (``backend.app.api.schemas.contracts``).

``simulate_rotation`` es el callback que llama ``execute_comparison``::

    kernel(climate=ClimateSeason, soil=SoilProfile, rotation=RotationSchedule,
           assumptions=ModelAssumptions) -> dict

Devuelve solo los campos numéricos del contrato (``Metrics`` y ``DailyBalance``
tienen ``extra='forbid'``, D8). ``simulate_rotation_detailed`` agrega el riego
requerido (corrida managed, D1) y el desglose por cultivo para la UI y el
backtest; no forma parte del contrato v0.1.0.

Período simulado = ``climate.start..climate.end`` completo (D7): los días fuera
de los ciclos son barbecho (D5). No predice rendimientos.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import pandas as pd

from backend.app.api.schemas.contracts import (
    ClimateSeason,
    CropCycle,
    ModelAssumptions,
    RotationSchedule,
    SoilProfile,
)
from backend.app.simulation.contract import (
    CropLibrary,
    CropParameters,
    KernelAssumptions,
    RotationLibrary,
    SoilWaterProfile,
)
from backend.app.simulation.et0 import et0_for_days
from backend.app.simulation.parameters import load_crops, load_rotations
from backend.app.simulation.version import MODEL_VERSION
from backend.app.simulation.water_balance import CycleWindow, simulate_cycles

ROOT = Path(__file__).resolve().parents[3]
CROPS_YAML = ROOT / "research" / "parameters" / "crops.yaml"
ROTATIONS_YAML = ROOT / "research" / "parameters" / "rotations.yaml"

#: Punto provisional de Abe (Guanacaste); elevación de la celda POWER/MERRA-2.
DEFAULT_LATITUDE_DEG = 10.55
DEFAULT_ELEVATION_M = 94.64
#: Hueco máximo (días) que se interpola; más largo deja el balance en null.
MAX_GAP_DAYS = 3
#: Diferencia relativa de duración de ciclo vs. YAML que dispara warning.
STAGE_SCALE_TOLERANCE = 0.10
#: ``crop_id`` del contrato → entrada de ``crops.yaml``.
DEFAULT_PARAMETER_SET = {"rice": "rice", "melon": "melon", "legume": "cowpea", "sorghum": "sorghum"}
FAO56_REF = "FAO-56 (Allen et al., 1998), https://www.fao.org/3/x0490e/x0490e00.htm"
#: Necesidad hídrica estacional orientativa [mm] (FAO Irrigation Water Management,
#: Training manual 3, Brouwer & Heibloem 1986, Tabla 13). Legume = "beans". Solo control.
SEASONAL_ETC_RANGE_MM = {"rice": (450, 700), "melon": (400, 600), "legume": (300, 500),
                         "sorghum": (450, 650)}
SEASONAL_ETC_REF = ("FAO Irrigation Water Management, Training manual 3 (Brouwer & Heibloem, "
                    "1986), Tabla 13: https://www.fao.org/3/s2022e/s2022e00.htm")


@lru_cache(maxsize=1)
def _default_crops() -> CropLibrary:
    return load_crops(CROPS_YAML)


@lru_cache(maxsize=1)
def _default_rotations() -> RotationLibrary:
    return load_rotations(ROTATIONS_YAML)


# --------------------------------------------------------------------------- #
# Clima
# --------------------------------------------------------------------------- #


def _runs(mask: list[bool]) -> list[tuple[int, int]]:
    """Corridas ``(inicio, largo)`` de valores True."""
    runs, start = [], None
    for index, flag in enumerate(mask + [False]):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            runs.append((start, index - start))
            start = None
    return runs


def _fill_short_gaps(values: list[float | None], label: str, *, rain: bool,
                     warnings: list[str], dates: list[date]) -> tuple[list[float | None], int | None]:
    """Rellena huecos ≤ MAX_GAP_DAYS; devuelve la serie y el índice del primer hueco largo."""
    series = list(values)
    first_long: int | None = None
    for start, length in _runs([value is None for value in series]):
        span = f"{dates[start]}..{dates[start + length - 1]}"
        if length > MAX_GAP_DAYS:
            warnings.append(
                f"{label}: hueco de {length} días ({span}) > {MAX_GAP_DAYS}; "
                "el balance queda null desde ese día y las métricas totales en null."
            )
            first_long = start if first_long is None else min(first_long, start)
            continue
        if rain:
            fill = [0.0] * length
            warnings.append(f"{label}: hueco de {length} día(s) ({span}) rellenado con 0 mm.")
        else:
            left = series[start - 1] if start > 0 else None
            right = series[start + length] if start + length < len(series) else None
            if left is None and right is None:
                first_long = start if first_long is None else min(first_long, start)
                continue
            left = right if left is None else left
            right = left if right is None else right
            fill = [left + (right - left) * (i + 1) / (length + 1) for i in range(length)]
            warnings.append(f"{label}: hueco de {length} día(s) ({span}) interpolado linealmente.")
        series[start:start + length] = fill
    return series, first_long


def _climate_frame(climate: ClimateSeason, latitude_deg: float, elevation_m: float,
                   warnings: list[str], assumptions_text: list[str]) -> tuple[pd.DataFrame, int | None]:
    dates = [day.date for day in climate.days]
    given = [day.et0_mm for day in climate.days]
    computed: list[float | None] = given
    if any(value is None for value in given):
        rows = [day.model_dump() for day in climate.days]
        pm = et0_for_days(rows, latitude_deg, elevation_m)
        computed = [g if g is not None else c for g, c in zip(given, pm)]
        n = sum(value is None for value in given)
        assumptions_text.append(
            f"ET0 FAO-56 Penman-Monteith (Eq. 6, G = 0) calculada en el kernel para {n} día(s) "
            f"sin et0_mm, lat {latitude_deg}°, elevación {elevation_m} m."
        )
        if latitude_deg == DEFAULT_LATITUDE_DEG and elevation_m == DEFAULT_ELEVATION_M:
            warnings.append(
                "ET0 calculada con el sitio por defecto (10.55, −85.5; 94.64 m, celda POWER): "
                "el contrato no trae latitud/elevación."
            )
    else:
        assumptions_text.append("ET0 tomada de climate.days[].et0_mm (artefacto externo).")
    et0, long_et0 = _fill_short_gaps(computed, "ET0", rain=False, warnings=warnings, dates=dates)
    rain, long_rain = _fill_short_gaps(
        [day.precipitation_mm for day in climate.days], "precipitación", rain=True,
        warnings=warnings, dates=dates,
    )
    cut = min((i for i in (long_et0, long_rain) if i is not None), default=None)
    frame = pd.DataFrame({"date": dates, "rain_mm": rain, "et0_mm": et0})
    return frame, cut


# --------------------------------------------------------------------------- #
# Suelo, cultivos y supuestos
# --------------------------------------------------------------------------- #


def _soil(soil: SoilProfile, warnings: list[str]) -> SoilWaterProfile:
    fc, wp = soil.field_capacity_m3_m3, soil.wilting_point_m3_m3
    if fc is None or wp is None:
        fallback = SoilWaterProfile.from_soilgrids(None, None, "loam")
        warnings.append(
            "suelo sin θfc/θwp en el contrato: se usan defaults FAO-56 Tabla 19 (loam, "
            f"θfc={fallback.theta_fc}, θwp={fallback.theta_wp})."
        )
        return fallback
    return SoilWaterProfile(
        theta_fc=fc, theta_wp=wp,
        source="; ".join(soil.source_refs) or "contrato SoilProfile",
    )


def scale_stage_days(stage_days: list[int], duration: int) -> list[int]:
    """Escala [ini, dev, mid, late] a ``duration`` días, conservando la suma exacta."""
    total = sum(stage_days)
    if duration < len(stage_days):
        raise ValueError(f"ciclo de {duration} días demasiado corto para 4 etapas")
    scaled = [max(1, round(days * duration / total)) for days in stage_days]
    scaled[-1] += duration - sum(scaled)
    while scaled[-1] < 1:  # redondeos que se comen la última etapa
        largest = max(range(3), key=lambda i: scaled[i])
        scaled[largest] -= 1
        scaled[-1] += 1
    return scaled


def _params_complete(params: CropParameters) -> bool:
    return all(
        value is not None
        for value in (params.kc_ini, params.kc_mid, params.kc_end, params.stage_days,
                      params.root_depth_max_m, params.p_depletion)
    )


def _irrigated_crops(rotation_id: str) -> set[str]:
    """Segmentos regados en la corrida managed (D1), según ``rotations.yaml``."""
    template = next(r for r in _default_rotations().rotations if r.rotation_id == rotation_id)
    reverse = {v: k for k, v in DEFAULT_PARAMETER_SET.items()}
    return {reverse.get(s.crop_id, s.crop_id) for s in template.segments if s.irrigated}


def _cycles(rotation: RotationSchedule, crops: CropLibrary, soil: SoilProfile,
            warnings: list[str], assumptions_text: list[str],
            refs: list[str]) -> list[tuple[CropCycle, CycleWindow | None]]:
    irrigated = _irrigated_crops(rotation.rotation_id)
    out: list[tuple[CropCycle, CycleWindow | None]] = []
    for cycle in rotation.cycles:
        key = cycle.parameter_set_id
        if key is None:
            key = DEFAULT_PARAMETER_SET[cycle.crop_id]
            warnings.append(
                f"{cycle.crop_id}: parameter_set_id null; se usa el default '{key}' de crops.yaml."
            )
        if key not in crops.crops:
            raise KeyError(f"parameter_set_id '{key}' no existe en crops.yaml")
        params = crops.crops[key]
        if not _params_complete(params):
            warnings.append(f"parámetros faltantes para {cycle.crop_id}; el ciclo se simula como barbecho.")
            out.append((cycle, None))
            continue
        if params.source:
            refs.append(f"crops.yaml/{key}: {' '.join(params.source.split())}")
        if not params.verified:
            warnings.append(f"parámetros de '{key}' con verified: false (pendiente revisión I3).")
        warnings.extend(params.warnings)

        duration = (cycle.harvest_date - cycle.sowing_date).days + 1
        yaml_total = sum(params.stage_days)
        stages = scale_stage_days(params.stage_days, duration)
        if abs(duration - yaml_total) / yaml_total > STAGE_SCALE_TOLERANCE:
            warnings.append(
                f"{cycle.crop_id}: ciclo de {duration} días vs {yaml_total} del YAML "
                f"(>{STAGE_SCALE_TOLERANCE:.0%}); etapas escaladas a {stages}."
            )
        # Lo específico de cada rotación va a warnings / per_crop: execute_comparison
        # exige ``assumptions`` idénticos entre rotaciones pareadas del mismo año.
        root = params.root_depth_max_m
        if soil.rooting_depth_m is not None and soil.rooting_depth_m < root:
            warnings.append(
                f"{cycle.crop_id}: Zr limitada por el suelo a {soil.rooting_depth_m} m "
                f"(YAML {root} m)."
            )
            root = soil.rooting_depth_m
        window = CycleWindow(
            crop_id=cycle.crop_id,
            params=params.model_copy(update={"stage_days": stages, "root_depth_max_m": root}),
            sowing=cycle.sowing_date,
            end=cycle.harvest_date,
            irrigated=cycle.crop_id in irrigated,
            regime="upland",
        )
        out.append((cycle, window))
    return out


def _kernel_assumptions(assumptions: ModelAssumptions, warnings: list[str],
                        assumptions_text: list[str]) -> KernelAssumptions:
    fraction = assumptions.initial_soil_water_fraction
    if fraction is None:
        warnings.append("initial_soil_water_fraction null: Dr0 = 0 (perfil a capacidad de campo).")
        depletion = 0.0
    else:
        depletion = 1.0 - fraction
    base = KernelAssumptions(initial_depletion_fraction=depletion)
    assumptions_text.extend([
        f"Dr0 = {depletion:.2f}·TAW (1 − initial_soil_water_fraction).",
        f"Escorrentía D3: RO = {base.runoff_fraction}·max(0, P − {base.runoff_threshold_mm:g} mm).",
        "Arroz de secano (upland), no inundado (D2).",
        "Zr constante por ciclo (D4).",
        f"Barbecho fuera de los ciclos (D5): kc {base.kc_fallow}, Zr 0.15 m, p 0.5.",
        "Ks por Eq. 84; ETa = Ks·ETc; día con estrés = Ks < 1.",
        "Métricas totales solo sobre días de cultivo; el barbecho entra al balance pero no suma.",
    ])
    return base


# --------------------------------------------------------------------------- #
# Métricas
# --------------------------------------------------------------------------- #


def _metrics(rows: pd.DataFrame) -> dict:
    crop = rows[rows["crop_id"].notna()]
    return {
        "crop_water_demand_mm": round(float(crop["etc_mm"].sum()), 3),
        "modeled_water_deficit_mm": round(float(max(0.0, (crop["etc_mm"] - crop["eta_mm"]).sum())), 3),
        "water_stress_days": int((crop["ks"] < 1.0).sum()),
    }


NULL_METRICS = {"crop_water_demand_mm": None, "modeled_water_deficit_mm": None, "water_stress_days": None}


def _run(climate, soil, rotation, assumptions, crops, elevation_m, latitude_deg, *, detailed):
    crops = crops or _default_crops()
    warnings: list[str] = []
    text: list[str] = []
    refs: list[str] = [FAO56_REF]

    frame, cut = _climate_frame(climate, latitude_deg, elevation_m, warnings, text)
    water = _soil(soil, warnings)
    refs.extend(soil.source_refs)
    kernel_assumptions = _kernel_assumptions(assumptions, warnings, text)
    pairs = _cycles(rotation, crops, soil, warnings, text, refs)
    windows = [w for _, w in pairs if w is not None]

    mode = assumptions.irrigation_mode
    schedule = None
    if mode == "scheduled":
        schedule = dict(assumptions.irrigation_mm_by_date)
        text.append(f"Riego programado: {len(schedule)} fecha(s), {sum(schedule.values()):g} mm.")
    elif mode == "unspecified":
        warnings.append("manejo de riego no especificado: se simula como secano (rainfed).")
        text.append("Corrida rainfed (D1): sin riego.")
    else:
        text.append("Corrida rainfed (D1): sin riego.")

    usable = frame if cut is None else frame.iloc[:cut]
    if usable.empty:
        balance = pd.DataFrame(columns=["date", "crop_id", "etc_mm", "eta_mm", "ks", "taw_mm", "depletion_mm"])
    else:
        balance = simulate_cycles(usable, water, windows, kernel_assumptions,
                                  mode="rainfed", irrigation_by_date=schedule)
        warnings.extend(w for w in balance.attrs["warnings"] if not w.startswith("Dr inicial"))

    daily = []
    by_date = {row.date: row for row in balance.itertuples(index=False)}
    for day in frame["date"]:
        row = by_date.get(day)
        if row is None:
            daily.append({"date": day, "crop_water_demand_mm": None, "modeled_water_deficit_mm": None,
                          "soil_water_storage_mm": None, "water_stress": None})
            continue
        in_crop = isinstance(row.crop_id, str)  # barbecho llega como NaN desde pandas
        daily.append({
            "date": day,
            "crop_water_demand_mm": round(float(row.etc_mm), 4),
            "modeled_water_deficit_mm": round(max(0.0, float(row.etc_mm - row.eta_mm)), 4),
            "soil_water_storage_mm": round(max(0.0, float(row.taw_mm - row.depletion_mm)), 4),
            "water_stress": bool(row.ks < 1.0) if in_crop else None,
        })

    metrics = NULL_METRICS.copy() if cut is not None else _metrics(balance)

    per_crop = []
    for cycle, window in pairs:
        entry = {"crop_id": cycle.crop_id, "sowing_date": cycle.sowing_date,
                 "harvest_date": cycle.harvest_date, "simulated": window is not None,
                 "stage_days": list(window.params.stage_days) if window is not None else None,
                 "root_depth_m": window.params.root_depth_max_m if window is not None else None}
        rows = balance[(balance["date"] >= cycle.sowing_date) & (balance["date"] <= cycle.harvest_date)] \
            if not balance.empty else balance
        complete = window is not None and len(rows) == (cycle.harvest_date - cycle.sowing_date).days + 1
        entry.update(_metrics(rows) if complete else NULL_METRICS)
        per_crop.append(entry)
        low, high = SEASONAL_ETC_RANGE_MM[cycle.crop_id]
        etc = entry["crop_water_demand_mm"]
        if etc is not None and not low <= etc <= high:
            duration = len(rows)
            mean_et0 = float(rows["et0_mm"].mean())
            warnings.append(
                f"{cycle.crop_id}: ETc estacional {etc:.0f} mm fuera del rango FAO orientativo "
                f"{low}–{high} mm (ciclo de {duration} días, ET0 media {mean_et0:.1f} mm/día)."
            )
            refs.append(SEASONAL_ETC_REF)

    result = {
        "metrics": metrics,
        "daily_balance": daily,
        "assumptions": list(dict.fromkeys(text)),
        "source_refs": list(dict.fromkeys(refs)),
        "warnings": list(dict.fromkeys(warnings)),
        "model_version": MODEL_VERSION,
    }
    if not detailed:
        return result

    irrigation_requirement = None
    if cut is None and windows:
        managed = simulate_cycles(frame, water, windows, kernel_assumptions, mode="managed")
        irrigation_requirement = round(float(managed["irrigation_mm"].sum()), 3)
        result["assumptions"].append(
            "irrigation_requirement_mm: corrida managed (D1), refill_at_raw solo en segmentos "
            "regados de rotations.yaml."
        )
    result["irrigation_requirement_mm"] = irrigation_requirement
    result["per_crop"] = per_crop
    return result


def simulate_rotation(*, climate: ClimateSeason, soil: SoilProfile, rotation: RotationSchedule,
                      assumptions: ModelAssumptions, crops: CropLibrary | None = None,
                      elevation_m: float | None = None,
                      latitude_deg: float | None = None) -> dict:
    """Corre el balance FAO-56 de una rotación; salida compatible con ``execute_comparison``."""
    return _run(climate, soil, rotation, assumptions, crops,
                DEFAULT_ELEVATION_M if elevation_m is None else elevation_m,
                DEFAULT_LATITUDE_DEG if latitude_deg is None else latitude_deg, detailed=False)


def simulate_rotation_detailed(*, climate: ClimateSeason, soil: SoilProfile,
                               rotation: RotationSchedule, assumptions: ModelAssumptions,
                               crops: CropLibrary | None = None, elevation_m: float | None = None,
                               latitude_deg: float | None = None) -> dict:
    """Como :func:`simulate_rotation` + ``irrigation_requirement_mm`` y ``per_crop`` (fuera del contrato)."""
    return _run(climate, soil, rotation, assumptions, crops,
                DEFAULT_ELEVATION_M if elevation_m is None else elevation_m,
                DEFAULT_LATITUDE_DEG if latitude_deg is None else latitude_deg, detailed=True)


def template_rotation(rotation_id: str, year: int, *, sowing_dates: dict[str, date] | None = None,
                      crops: CropLibrary | None = None,
                      calendar_status: str = "provisional") -> RotationSchedule:
    """Calendario de contrato desde ``rotations.yaml``: siembra MM-DD + suma de etapas del YAML.

    ``sowing_dates`` permite fijar siembras por ``crop_id`` del contrato. Útil para
    backtests y pruebas; el calendario oficial lo entrega el pipeline de Abe.
    """
    crops = crops or _default_crops()
    template = next(r for r in _default_rotations().rotations if r.rotation_id == rotation_id)
    reverse = {v: k for k, v in DEFAULT_PARAMETER_SET.items()}
    cycles = []
    for segment in template.segments:
        crop_id = reverse.get(segment.crop_id, segment.crop_id)
        month, day = (int(p) for p in segment.sowing_mmdd.split("-"))
        sowing = (sowing_dates or {}).get(crop_id) or date(year, month, day)
        length = sum(crops.crops[segment.crop_id].stage_days)
        cycles.append(CropCycle(crop_id=crop_id, sowing_date=sowing,
                                harvest_date=sowing + timedelta(days=length - 1),
                                parameter_set_id=segment.crop_id))
    return RotationSchedule(rotation_id=rotation_id, calendar_status=calendar_status, cycles=cycles)
