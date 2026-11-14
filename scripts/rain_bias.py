"""Lluvia de contraste: POWER frente a CHIRPS v3 y la media IMN de Liberia (tarea 4.8).

Compara totales anuales y la climatología mensual en el punto de la finca. No
corrige ninguna serie: solo mide la diferencia para documentarla.

Uso:
    python -m scripts.rain_bias --output-dir docs

Requiere haber corrido antes ``python -m scripts.ingest_chirps``. Escribe
``rain_bias.csv`` y ``rain_bias.png`` en ``<output-dir>/rain_bias/``. El texto
interpretativo de ``docs/rain_bias.md`` se escribe a mano a partir de esos números.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from scripts.ingest_chirps import OUTPUT as CHIRPS_FILE
from scripts.sensitivity import CLIMATE_DIR

ROOT = Path(__file__).resolve().parents[1]
#: Media anual IMN, estación Liberia (dato del equipo, ver docs/rain_bias.md).
IMN_LIBERIA_MM = 1652.7
FIRST_YEAR, LAST_YEAR = 1981, 2025


def power_monthly() -> dict[tuple[int, int], tuple[float, int]]:
    """(año, mes) → (suma mm, días sin dato)."""
    totals: dict[tuple[int, int], list] = defaultdict(lambda: [0.0, 0])
    for path in sorted(CLIMATE_DIR.glob("power_10.55_-85.5_*-01-01_*-12-31.json")):
        for row in json.loads(path.read_text(encoding="utf-8"))["days"]:
            key = (int(row["date"][:4]), int(row["date"][5:7]))
            if row.get("precipitation_mm") is None:
                totals[key][1] += 1
            else:
                totals[key][0] += row["precipitation_mm"]
    return {k: (round(v[0], 2), v[1]) for k, v in totals.items()}


def chirps_monthly(path: Path = CHIRPS_FILE) -> dict[tuple[int, int], float | None]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return {(int(r["month"][:4]), int(r["month"][5:])): r["precipitation_mm"] for r in document["months"]}


def annual_table(power: dict, chirps: dict, years: range) -> list[dict]:
    rows = []
    for year in years:
        p_months = [power.get((year, m)) for m in range(1, 13)]
        c_months = [chirps.get((year, m)) for m in range(1, 13)]
        p_ok = all(v is not None and v[1] == 0 for v in p_months)
        c_ok = all(v is not None for v in c_months)
        p = round(sum(v[0] for v in p_months), 1) if p_ok else None
        c = round(sum(c_months), 1) if c_ok else None
        ratio = None if not (p and c) else round(p / c, 3)
        rows.append({"year": year, "power_mm": p, "chirps_mm": c, "power_over_chirps": ratio})
    return rows


def monthly_climatology(power: dict, chirps: dict, years: range) -> list[dict]:
    out = []
    for month in range(1, 13):
        p = [power[(y, month)][0] for y in years if (y, month) in power and power[(y, month)][1] == 0]
        c = [chirps[(y, month)] for y in years if chirps.get((y, month)) is not None]
        out.append({"month": month, "power_mm": round(mean(p), 1) if p else None,
                    "chirps_mm": round(mean(c), 1) if c else None})
    return out


def write_png(rows: list[dict], climatology: list[dict], path: Path) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.4), gridspec_kw={"width_ratios": [2.2, 1]})
    years = [r["year"] for r in rows]
    ax1.plot(years, [r["power_mm"] for r in rows], marker="o", ms=3, color="#c8742c", label="NASA POWER (PRECTOTCORR)")
    ax1.plot(years, [r["chirps_mm"] for r in rows], marker="o", ms=3, color="#2a78b5", label="CHIRPS v3 (2×2 celdas)")
    ax1.axhline(IMN_LIBERIA_MM, color="black", ls="--", lw=1, label=f"Media IMN Liberia ({IMN_LIBERIA_MM:.0f} mm)")
    ax1.set_ylabel("mm/año")
    ax1.set_title("Lluvia anual en 10.55, −85.50", fontsize=10)
    ax1.grid(alpha=0.3)
    ax1.legend(fontsize=8)
    months = "EFMAMJJASOND"
    x = range(12)
    ax2.bar([i - 0.2 for i in x], [c["power_mm"] for c in climatology], width=0.4, color="#c8742c", label="POWER")
    ax2.bar([i + 0.2 for i in x], [c["chirps_mm"] for c in climatology], width=0.4, color="#2a78b5", label="CHIRPS v3")
    ax2.set_xticks(list(x), list(months))
    ax2.set_ylabel("mm/mes")
    ax2.set_title(f"Media mensual {FIRST_YEAR}–{LAST_YEAR}", fontsize=10)
    ax2.grid(axis="y", alpha=0.3)
    ax2.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return True


def summary(rows: list[dict]) -> dict:
    both = [r for r in rows if r["power_mm"] is not None and r["chirps_mm"] is not None]
    power_mean = mean(r["power_mm"] for r in both)
    chirps_mean = mean(r["chirps_mm"] for r in both)
    return {"n_years": len(both), "power_mean": round(power_mean, 1), "chirps_mean": round(chirps_mean, 1),
            "power_vs_chirps_pct": round(100 * (power_mean / chirps_mean - 1), 1),
            "power_vs_imn_pct": round(100 * (power_mean / IMN_LIBERIA_MM - 1), 1),
            "chirps_vs_imn_pct": round(100 * (chirps_mean / IMN_LIBERIA_MM - 1), 1),
            "years_power_below_chirps": sum(r["power_mm"] < r["chirps_mm"] for r in both)}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs")
    args = parser.parse_args(argv)
    power, chirps = power_monthly(), chirps_monthly()
    years = range(FIRST_YEAR, LAST_YEAR + 1)
    rows = annual_table(power, chirps, years)
    climatology = monthly_climatology(power, chirps, years)
    out = args.output_dir / "rain_bias"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "rain_bias.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    png = write_png(rows, climatology, out / "rain_bias.png")
    print(json.dumps(summary(rows), ensure_ascii=False))
    print("mensual:", json.dumps(climatology))
    print(f"→ {out}" + ("" if png else " (sin PNG: falta matplotlib)"))


if __name__ == "__main__":
    main()
