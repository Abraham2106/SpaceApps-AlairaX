"""Backtest del método de análogos (tarea 4.6).

Para cada año objetivo T (por defecto 2015 y 2023):

  (a) "verdad del modelo": el kernel FAO-56 corrido con el clima real de la temporada T.
  (b) ensamble: el kernel corrido con los k años análogos que devuelve
      ``find_analogs`` de Abe, con T fuera del conjunto de candidatos.

Se reporta si (a) cae dentro de p10–p90 de (b) y el error absoluto de p50. Como
referencia se agrega la climatología: el mismo cálculo con todos los años
candidatos en lugar de los k análogos. Si los análogos no se acercan más que la
climatología, no aportan información para ese año y esa métrica.

Esto valida el método de análogos contra el propio modelo, no la precisión de
campo: la "verdad" es una salida del kernel, no una medición.

Detalles:
  - ``find_analogs`` solo admite candidatos anteriores al año objetivo, así que
    para 2015 el conjunto es 1984–2014. Es más estricto que dejar un año fuera.
  - Features con la misma ventana del pipeline de Abe: 01-abr a 31-oct, ONI ASO,
    umbral de calor 35 °C.
  - Temporada del kernel: mayo T a abril T+1, suelo loam FAO-56, secano (D1),
    siembras fijas de ``scripts.sensitivity`` (arroz 15-may, caupí y sorgo 15-oct).

Uso:
    python -m scripts.backtest --targets 2015 2023 --k 3 5 --output-dir docs/backtest

Escribe ``backtest.csv``, ``backtest.md`` y ``backtest.png`` (si hay matplotlib).
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from backend.app.api.schemas.contracts import ModelAssumptions
from backend.app.intelligence.analog_knn import find_analogs
from backend.app.intelligence.features import SeasonFeatures, build_season_features
from backend.app.intelligence.robustness import summarize
from backend.app.simulation.contract import SoilWaterProfile
from backend.app.simulation.kernel import _default_crops, simulate_rotation_detailed, template_rotation
from backend.app.simulation.version import MODEL_VERSION
from scripts.build_analogs import load_normalized_climate, load_normalized_oni
from scripts.sensitivity import CLIMATE_DIR, ET0_FILE, ROTATIONS, SOWING, load_season, soil_for, CASES

ROOT = Path(__file__).resolve().parents[1]
ONI_FILE = ROOT / "datasets" / "processed" / "climate" / "oni.json"
WINDOW = ((4, 1), (10, 31))
ONI_SEASON = "ASO"
HEAT_THRESHOLD_C = 35.0
DEFAULT_TARGETS = (2015, 2023)
DEFAULT_KS = (3, 5)
#: Último año con temporada completa mayo–abril en la descarga POWER.
LAST_SEASON_YEAR = 2025
METRICS = {
    "modeled_water_deficit_mm": "Déficit (mm)",
    "crop_water_demand_mm": "ETc (mm)",
    "water_stress_days": "Días de estrés hídrico",
    "irrigation_requirement_mm": "Riego requerido (mm)",
    "heat_stress_days": "Días de estrés térmico",
}


def load_features(et0: dict[str, float | None]) -> tuple[list[SeasonFeatures], list[dict]]:
    """Features por año con la ventana del pipeline de Abe y la ET0 de Justin."""
    climate_files = sorted(CLIMATE_DIR.glob("power_10.55_-85.5_*-01-01_*-12-31.json"))
    _, _, days = load_normalized_climate(climate_files)
    _, _, anomalies = load_normalized_oni(ONI_FILE, False, ONI_SEASON)
    features, excluded = [], []
    for year in sorted({d.year for d in days}):
        start, end = date(year, *WINDOW[0]), date(year, *WINDOW[1])
        rows = [row | {"et0_mm": et0.get(day.isoformat())} for day, row in days.items()
                if start <= day <= end]
        try:
            features.append(build_season_features(rows, year=year, start=start, end=end,
                                                  oni=anomalies.get(year), oni_season=ONI_SEASON,
                                                  heat_threshold_c=HEAT_THRESHOLD_C))
        except ValueError as error:
            excluded.append({"year": year, "reason": str(error)})
    return features, excluded


class SeasonRunner:
    """Corre (y guarda) el kernel por año y rotación con la base de la sensibilidad."""

    def __init__(self, et0: dict[str, float | None]):
        self.et0 = et0
        self.crops = _default_crops()
        self.soil = soil_for(CASES[0], SoilWaterProfile.from_soilgrids(None, None, "loam"))
        self.assumptions = ModelAssumptions(irrigation_mode="rainfed", irrigation_mm_by_date={},
                                            initial_soil_water_fraction=0.5, notes=[])
        self._cache: dict[int, dict[str, dict]] = {}

    def __call__(self, year: int) -> dict[str, dict]:
        if year not in self._cache:
            climate = load_season(year, self.et0)
            sowing = {crop: date(year, m, d) for crop, (m, d) in SOWING.items()}
            out = {}
            for rotation_id in ROTATIONS:
                rotation = template_rotation(rotation_id, year, sowing_dates=sowing, crops=self.crops)
                result = simulate_rotation_detailed(climate=climate, soil=self.soil, rotation=rotation,
                                                    assumptions=self.assumptions, crops=self.crops)
                values = dict(result["metrics"])
                values["irrigation_requirement_mm"] = result["irrigation_requirement_mm"]
                values["heat_stress_days"] = result["heat_stress_days"]
                out[rotation_id] = values
            self._cache[year] = out
        return self._cache[year]


@dataclass
class Row:
    target: int
    k: int
    rotation_id: str
    metric: str
    truth: float | None
    analog_years: tuple[int, ...]
    p10: float | None
    p50: float | None
    p90: float | None
    clim_p10: float | None
    clim_p50: float | None
    clim_p90: float | None
    n_clim: int

    @property
    def inside(self) -> bool | None:
        if None in (self.truth, self.p10, self.p90):
            return None
        return self.p10 <= self.truth <= self.p90

    @property
    def abs_error(self) -> float | None:
        return None if None in (self.truth, self.p50) else abs(self.p50 - self.truth)

    @property
    def clim_abs_error(self) -> float | None:
        return None if None in (self.truth, self.clim_p50) else abs(self.clim_p50 - self.truth)

    @property
    def clim_inside(self) -> bool | None:
        if None in (self.truth, self.clim_p10, self.clim_p90):
            return None
        return self.clim_p10 <= self.truth <= self.clim_p90


def backtest(targets: list[int], ks: list[int], features: list[SeasonFeatures],
             run: SeasonRunner) -> tuple[list[Row], dict]:
    by_year = {f.year: f for f in features}
    rows, selections = [], {}
    for target in targets:
        if target not in by_year:
            raise ValueError(f"{target}: sin features completas en la ventana; no se puede evaluar")
        if target > LAST_SEASON_YEAR:
            raise ValueError(f"{target}: la temporada mayo–abril no está completa")
        # find_analogs ya descarta el año objetivo y los posteriores; se quita T de forma explícita igual.
        candidates = [f for f in features if f.year != target]
        truth = run(target)
        for k in ks:
            result = find_analogs(candidates, by_year[target], k=k)
            years = tuple(n["year"] for n in result["neighbors"])
            pool = result["candidate_years"]
            selections[(target, k)] = {"years": years, "distances": [round(n["distance"], 3)
                                       for n in result["neighbors"]], "pool": pool}
            for rotation_id in ROTATIONS:
                for metric in METRICS:
                    ens = summarize([run(y)[rotation_id][metric] for y in years])
                    clim = summarize([run(y)[rotation_id][metric] for y in pool])
                    rows.append(Row(target, k, rotation_id, metric, truth[rotation_id][metric], years,
                                    ens.p10, ens.p50, ens.p90, clim.p10, clim.p50, clim.p90, clim.n))
    return rows, selections


def _num(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}".replace(".", ",")


def _yes(value: bool | None) -> str:
    return "—" if value is None else ("sí" if value else "no")


def _relevant(row: Row) -> bool:
    """El riego solo existe en rice_melon y el estrés térmico solo en arroz (igual en las tres)."""
    if row.metric == "irrigation_requirement_mm":
        return row.rotation_id == "rice_melon"
    return True


def write_csv(rows: list[Row], path: Path) -> None:
    fields = ["target", "k", "rotation_id", "metric", "truth", "p10", "p50", "p90", "inside_p10_p90",
              "abs_error_p50", "clim_p10", "clim_p50", "clim_p90", "clim_inside", "clim_abs_error_p50",
              "n_clim", "analog_years"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        for r in rows:
            writer.writerow([r.target, r.k, r.rotation_id, r.metric, r.truth, r.p10, r.p50, r.p90,
                             r.inside, r.abs_error, r.clim_p10, r.clim_p50, r.clim_p90, r.clim_inside,
                             r.clim_abs_error, r.n_clim, " ".join(map(str, r.analog_years))])


def write_markdown(rows: list[Row], selections: dict, ks: list[int], path: Path, *,
                   et0_reviewed: bool, png: bool) -> None:
    lines = [
        "# Backtest del método de análogos",
        "",
        f"Generado con `python -m scripts.backtest`, kernel `{MODEL_VERSION}`. Es una validación del "
        "**método de análogos contra el propio modelo**, no de precisión de campo: la \"verdad\" es el "
        "kernel corrido con el clima real del año objetivo, no una medición.",
        "",
    ]
    if not et0_reviewed:
        lines += ["> **Preliminar:** la ET0 usada tiene `reviewed: false`. Repetir cuando Justin la revise "
                  "y cuando Ant entregue suelo y calendarios.", ""]
    lines += [
        "Método:",
        "",
        "- Features con la ventana del pipeline de Abe (01-abr a 31-oct, ONI ASO, calor ≥35 °C) y pesos iguales.",
        "- `find_analogs` solo admite candidatos **anteriores** al año objetivo. Para 2015 el conjunto es "
        "1984–2014; es más estricto que dejar un año fuera.",
        "- Kernel: temporada mayo–abril, suelo loam FAO-56, secano (D1), arroz 15-may, caupí y sorgo 15-oct. "
        "Riego requerido con `simulate_rotation_detailed` (corrida managed).",
        "- Cuantiles empíricos entre años (`robustness.summarize`), no intervalos de confianza. Con k = 3 o 5, "
        "p10 y p90 quedan casi en el mínimo y el máximo del ensamble.",
        "- Referencia: climatología, el mismo cálculo con todos los años candidatos.",
        "",
        "## Años análogos",
        "",
        "| Objetivo | k | Análogos (distancia) | Candidatos |",
        "|---|---|---|---|",
    ]
    for (target, k), sel in sorted(selections.items()):
        pairs = ", ".join(f"{y} ({_num(d, 2)})" for y, d in zip(sel["years"], sel["distances"]))
        lines.append(f"| {target} | {k} | {pairs} | {sel['pool'][0]}–{sel['pool'][-1]} ({len(sel['pool'])}) |")

    lines += ["", "## Resumen", "",
              "Casos = combinaciones rotación × métrica con valor (el riego solo cuenta en `rice_melon`).", "",
              "| Objetivo | k | Casos | Verdad en p10–p90 (análogos) | Verdad en p10–p90 (climatología) | "
              "Análogos más cerca que la climatología (p50) |",
              "|---|---|---|---|---|---|"]
    for (target, k) in sorted(selections):
        subset = [r for r in rows if r.target == target and r.k == k and _relevant(r) and r.abs_error is not None]
        inside = sum(bool(r.inside) for r in subset)
        clim_inside = sum(bool(r.clim_inside) for r in subset)
        closer = sum(r.abs_error < r.clim_abs_error for r in subset if r.clim_abs_error is not None)
        lines.append(f"| {target} | {k} | {len(subset)} | {inside} | {clim_inside} | {closer} |")

    for k in ks:
        lines += ["", f"## Detalle, k = {k}", "",
                  "| Objetivo | Rotación | Métrica | Verdad | p10 | p50 | p90 | ¿Dentro? | Error p50 | "
                  "p50 climatología | Error climatología |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            if r.k != k or not _relevant(r):
                continue
            lines.append(f"| {r.target} | `{r.rotation_id}` | {METRICS[r.metric]} | {_num(r.truth)} | "
                         f"{_num(r.p10)} | {_num(r.p50)} | {_num(r.p90)} | {_yes(r.inside)} | "
                         f"{_num(r.abs_error)} | {_num(r.clim_p50)} | {_num(r.clim_abs_error)} |")
    lines += ["", "El estrés térmico se cuenta solo en la etapa `mid` del arroz, así que es igual en las tres rotaciones."]
    if png:
        lines += ["", "![Backtest: verdad del modelo frente al rango p10–p90 de los análogos](backtest.png)"]
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_png(rows: list[Row], k: int, path: Path) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    metrics = ["modeled_water_deficit_mm", "crop_water_demand_mm", "water_stress_days",
               "irrigation_requirement_mm"]
    targets = sorted({r.target for r in rows})
    fig, axes = plt.subplots(1, len(metrics), figsize=(4.2 * len(metrics), 4.2))
    colors = {"rice_melon": "#2a78b5", "rice_legume": "#3c9a5f", "rice_sorghum": "#c8742c"}
    for ax, metric in zip(axes, metrics):
        labels, x = [], 0
        for target in targets:
            for rotation_id in ROTATIONS:
                row = next((r for r in rows if r.k == k and r.target == target and r.metric == metric
                            and r.rotation_id == rotation_id), None)
                if row is None or not _relevant(row) or row.p50 is None:
                    continue
                color = colors[rotation_id]
                ax.plot([x, x], [row.clim_p10, row.clim_p90], color="#bbbbbb", lw=7, solid_capstyle="butt",
                        label="Climatología p10–p90" if not labels else None)
                ax.errorbar(x, row.p50, yerr=[[row.p50 - row.p10], [row.p90 - row.p50]], fmt="o",
                            color=color, capsize=4, label=None)
                if row.truth is not None:
                    ax.plot(x, row.truth, marker="X", color="black", ms=8, ls="none",
                            label="Verdad del modelo" if not labels else None)
                labels.append(f"{target}\n{rotation_id.replace('rice_', '')}")
                x += 1
        ax.set_xticks(range(len(labels)), labels, fontsize=8)
        ax.set_title(METRICS[metric], fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(fontsize=8, loc="best")
    fig.suptitle(f"Backtest de análogos (k = {k}): punto y barra = p50 y p10–p90 del ensamble", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--targets", type=int, nargs="+", default=list(DEFAULT_TARGETS))
    parser.add_argument("--k", type=int, nargs="+", default=list(DEFAULT_KS))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "backtest")
    args = parser.parse_args(argv)

    document = json.loads(ET0_FILE.read_text(encoding="utf-8"))
    features, _ = load_features(document["values"])
    # Solo años con temporada mayo–abril completa entran como análogos.
    features = [f for f in features if f.year <= LAST_SEASON_YEAR]
    rows, selections = backtest(args.targets, args.k, features, SeasonRunner(document["values"]))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(rows, args.output_dir / "backtest.csv")
    png = write_png(rows, max(args.k), args.output_dir / "backtest.png")
    write_markdown(rows, selections, args.k, args.output_dir / "backtest.md",
                   et0_reviewed=bool(document.get("reviewed")), png=png)
    print(f"{len(rows)} filas → {args.output_dir}" + ("" if png else " (sin PNG: falta matplotlib)"))


if __name__ == "__main__":
    main()
