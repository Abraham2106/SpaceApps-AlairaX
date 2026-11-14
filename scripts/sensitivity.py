"""Sensibilidad del kernel FAO-56 (tarea 3.7).

Varía un parámetro a la vez sobre temporadas POWER reales (mayo Y – abril Y+1) y
mide el cambio en las métricas de cada rotación frente a la corrida base. También
reporta si cambia el orden entre rotaciones dentro de cada año.

Casos:
  - Kc (ini, mid, end de todos los cultivos) ×0,9 y ×1,1.
  - Dr inicial 0; 0,5 (base) y 1·TAW.
  - θfc ±20 % y θwp ±20 %, por separado.
  - Lluvia ±28 % (sesgo POWER vs IMN reportado por el equipo).

Uso:
    python -m scripts.sensitivity --years 2013 2015 2023 --output-dir outputs/sensitivity

Escribe ``sensitivity.csv`` (formato largo) y ``sensitivity.md`` (resumen).
La ET0 viene de ``datasets/processed/et0``; si ese archivo tiene ``reviewed: false``,
el resumen lo dice: los resultados son preliminares.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from statistics import mean

from backend.app.api.schemas.contracts import ClimateDay, ClimateSeason, ModelAssumptions, SoilProfile
from backend.app.simulation.contract import CropLibrary, SoilWaterProfile
from backend.app.simulation.kernel import _default_crops, simulate_rotation_detailed, template_rotation
from backend.app.simulation.version import MODEL_VERSION

ROOT = Path(__file__).resolve().parents[1]
CLIMATE_DIR = ROOT / "datasets" / "processed" / "climate"
ET0_FILE = ROOT / "datasets" / "processed" / "et0" / "et0_10.55_-85.5.json"
ROTATIONS = ("rice_melon", "rice_legume", "rice_sorghum")
METRICS = ("crop_water_demand_mm", "modeled_water_deficit_mm", "water_stress_days",
           "irrigation_requirement_mm")
#: Siembras fijas que evitan el traslape arroz/segundo cultivo de rotations.yaml.
SOWING = {"rice": (5, 15), "legume": (10, 15), "sorghum": (10, 15)}
BASE_INITIAL_FRACTION = 0.5  # Dr0 = 0,5·TAW
DEFAULT_YEARS = (2013, 2015, 2023)
RAIN_BIAS = 0.28


@dataclass(frozen=True)
class Case:
    case_id: str
    group: str
    label: str
    kc: float = 1.0
    fc: float = 1.0
    wp: float = 1.0
    rain: float = 1.0
    initial_fraction: float = BASE_INITIAL_FRACTION


CASES = (
    Case("base", "base", "Base"),
    Case("kc_-10", "Kc", "Kc ×0,9", kc=0.9),
    Case("kc_+10", "Kc", "Kc ×1,1", kc=1.1),
    Case("dr0_0", "Dr inicial", "Dr0 = 0 (capacidad de campo)", initial_fraction=1.0),
    Case("dr0_1", "Dr inicial", "Dr0 = 1·TAW (punto de marchitez)", initial_fraction=0.0),
    Case("fc_-20", "θfc", "θfc ×0,8", fc=0.8),
    Case("fc_+20", "θfc", "θfc ×1,2", fc=1.2),
    Case("wp_-20", "θwp", "θwp ×0,8", wp=0.8),
    Case("wp_+20", "θwp", "θwp ×1,2", wp=1.2),
    Case("rain_-28", "Lluvia", f"Lluvia ×{1 - RAIN_BIAS:.2f}".replace(".", ","), rain=1 - RAIN_BIAS),
    Case("rain_+28", "Lluvia", f"Lluvia ×{1 + RAIN_BIAS:.2f}".replace(".", ","), rain=1 + RAIN_BIAS),
)


def load_season(year: int, et0: dict[str, float | None]) -> ClimateSeason:
    rows = []
    for y in (year, year + 1):
        path = CLIMATE_DIR / f"power_10.55_-85.5_{y}-01-01_{y}-12-31.json"
        rows += json.loads(path.read_text(encoding="utf-8"))["days"]
    start, end = date(year, 5, 1), date(year + 1, 4, 30)
    days = [ClimateDay(**(r | {"et0_mm": et0.get(r["date"])})) for r in rows
            if start <= date.fromisoformat(r["date"]) <= end]
    return ClimateSeason(year=year, start=start, end=end, days=days)


def scale_rain(climate: ClimateSeason, factor: float) -> ClimateSeason:
    if factor == 1.0:
        return climate
    days = [d.model_copy(update={"precipitation_mm": None if d.precipitation_mm is None
                                 else d.precipitation_mm * factor}) for d in climate.days]
    return climate.model_copy(update={"days": days})


def scale_kc(crops: CropLibrary, factor: float) -> CropLibrary:
    if factor == 1.0:
        return crops
    scaled = {}
    for key, params in crops.crops.items():
        update = {name: getattr(params, name) * factor for name in ("kc_ini", "kc_mid", "kc_end")
                  if getattr(params, name) is not None}
        scaled[key] = params.model_copy(update=update)
    return crops.model_copy(update={"crops": scaled})


def soil_for(case: Case, base: SoilWaterProfile) -> SoilProfile:
    fc, wp = base.theta_fc * case.fc, base.theta_wp * case.wp
    if fc <= wp:
        raise ValueError(f"{case.case_id}: θfc {fc:.3f} ≤ θwp {wp:.3f}")
    return SoilProfile(field_capacity_m3_m3=round(fc, 4), wilting_point_m3_m3=round(wp, 4),
                       rooting_depth_m=None, source_refs=[f"FAO-56 Tabla 19 loam ({case.case_id})"])


@dataclass
class Run:
    case: Case
    year: int
    rotation_id: str
    values: dict[str, float | int | None] = field(default_factory=dict)


def run_all(years: list[int], et0: dict) -> list[Run]:
    base_soil = SoilWaterProfile.from_soilgrids(None, None, "loam")
    base_crops = _default_crops()
    seasons = {year: load_season(year, et0) for year in years}
    runs = []
    for case in CASES:
        crops = scale_kc(base_crops, case.kc)
        soil = soil_for(case, base_soil)
        assumptions = ModelAssumptions(irrigation_mode="rainfed", irrigation_mm_by_date={},
                                       initial_soil_water_fraction=case.initial_fraction, notes=[])
        for year in years:
            climate = scale_rain(seasons[year], case.rain)
            sowing = {crop: date(year, m, d) for crop, (m, d) in SOWING.items()}
            for rotation_id in ROTATIONS:
                rotation = template_rotation(rotation_id, year, sowing_dates=sowing, crops=crops)
                result = simulate_rotation_detailed(climate=climate, soil=soil, rotation=rotation,
                                                    assumptions=assumptions, crops=crops)
                values = dict(result["metrics"])
                values["irrigation_requirement_mm"] = result["irrigation_requirement_mm"]
                runs.append(Run(case, year, rotation_id, values))
    return runs


def _ranking(values: dict[str, float | None]) -> tuple | None:
    """Orden de rotaciones por métrica (empates agrupados); None si falta algún valor."""
    if any(v is None for v in values.values()):
        return None
    levels = sorted({round(v, 3) for v in values.values()})
    return tuple(levels.index(round(values[r], 3)) for r in ROTATIONS)


def build_rows(runs: list[Run]) -> list[dict]:
    base = {(r.year, r.rotation_id): r.values for r in runs if r.case.case_id == "base"}
    rows = []
    for run in runs:
        for metric in METRICS:
            value, ref = run.values[metric], base[(run.year, run.rotation_id)][metric]
            delta = None if value is None or ref is None else value - ref
            pct = None if delta is None or ref == 0 else 100.0 * delta / ref
            rows.append({"case_id": run.case.case_id, "group": run.case.group, "year": run.year,
                         "rotation_id": run.rotation_id, "metric": metric, "value": value,
                         "baseline": ref, "delta": None if delta is None else round(delta, 3),
                         "delta_pct": None if pct is None else round(pct, 2)})
    return rows


def ranking_changes(runs: list[Run], years: list[int]) -> dict[tuple[str, str], int]:
    by_key = {(r.case.case_id, r.year, r.rotation_id): r.values for r in runs}
    changes = {}
    for case in CASES:
        for metric in METRICS:
            count = 0
            for year in years:
                ref = _ranking({rot: by_key[("base", year, rot)][metric] for rot in ROTATIONS})
                new = _ranking({rot: by_key[(case.case_id, year, rot)][metric] for rot in ROTATIONS})
                count += ref != new
            changes[(case.case_id, metric)] = count
    return changes


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1f} %".replace(".", ",")


def write_outputs(rows: list[dict], changes: dict, years: list[int], output_dir: Path,
                  et0_reviewed: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "sensitivity.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Sensibilidad del kernel FAO-56",
        "",
        f"Generado con `python -m scripts.sensitivity`, kernel `{MODEL_VERSION}`, temporadas "
        f"mayo–abril de {', '.join(map(str, years))} (POWER, punto 10.55, −85.5).",
        "",
        "Base: suelo loam FAO-56 Tabla 19, Dr0 = 0,5·TAW, secano (D1), siembras arroz 15-may, "
        "caupí y sorgo 15-oct, melón según `rotations.yaml`.",
        "",
    ]
    if not et0_reviewed:
        lines += ["> **Preliminar:** la ET0 usada tiene `reviewed: false`. Repetir cuando Justin la revise.", ""]
    lines += [
        "Cada celda: cambio medio frente a la base (todas las rotaciones y años) · años en que cambia "
        f"el orden entre rotaciones (de {len(years)}).",
        "",
        "| Caso | ETc | Déficit | Días de estrés | Riego requerido |",
        "|---|---|---|---|---|",
    ]
    for case in CASES[1:]:
        cells = []
        for metric in METRICS:
            pcts = [r["delta_pct"] for r in rows
                    if r["case_id"] == case.case_id and r["metric"] == metric and r["delta_pct"] is not None]
            mean_pct = mean(pcts) if pcts else None
            cells.append(f"{_fmt(mean_pct)} · {changes[(case.case_id, metric)]}")
        lines.append(f"| {case.label} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "El riego requerido solo es distinto de cero en `rice_melon` (melón regado). "
        "Un cambio de orden con métricas casi iguales puede ser un empate roto por redondeo; "
        "revisar `sensitivity.csv` antes de interpretarlo.",
        "",
    ]
    (output_dir / "sensitivity.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--years", type=int, nargs="+", default=list(DEFAULT_YEARS))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "sensitivity")
    args = parser.parse_args(argv)

    document = json.loads(ET0_FILE.read_text(encoding="utf-8"))
    runs = run_all(args.years, document["values"])
    rows = build_rows(runs)
    write_outputs(rows, ranking_changes(runs, args.years), args.years, args.output_dir,
                  bool(document.get("reviewed")))
    print(f"{len(runs)} corridas → {args.output_dir / 'sensitivity.csv'}, {args.output_dir / 'sensitivity.md'}")


if __name__ == "__main__":
    main()
