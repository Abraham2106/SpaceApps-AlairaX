import { useEffect, useId, useState } from "react";
import type { CompareResponse, Lang, MetricId, RotationComparison, RotationId } from "../lib/types";
import { formatNumber, formatSigned, formatValue, metricUnit } from "../lib/format";
import { ROTATION_ORDER, ROTATION_STYLE, rotationName } from "../lib/plain";
import { RadioGroup } from "./RadioGroup";

export type ComparisonView = "chart" | "table";
type Summary = RotationComparison["metrics"][MetricId];
type AnnualReading = { year: number; value: number | null };
type Reading = {
  id: RotationId;
  name: string;
  summary: Summary;
  annual: AnnualReading[];
};
type ValueFormat = (value: number | null) => string;

function RotationPlot({ rows, difference, metric, lang, format }: {
  rows: Reading[];
  difference: boolean;
  metric: MetricId;
  lang: Lang;
  format: ValueFormat;
}) {
  const chartId = useId();
  const [active, setActive] = useState<RotationId | null>(null);
  const spanish = lang === "es";
  const values = rows.flatMap(({ summary, annual }) => [
    summary.p10, summary.p50, summary.p90, ...annual.map(({ value }) => value),
  ]).filter((value) => value !== null);
  const extent = Math.max(1, ...values.map(Math.abs)) * 1.08;
  const step = 10 ** Math.floor(Math.log10(extent / 5));
  const max = Math.ceil(extent / step) * step;
  const min = difference ? -max : 0;
  const position = (value: number) => ((value - min) / (max - min)) * 100;
  const ticks = [min, (min + max) / 2, max];

  useEffect(() => {
    if (active === null) return;
    const dismiss = (event: KeyboardEvent) => {
      if (event.key === "Escape") setActive(null);
    };
    document.addEventListener("keydown", dismiss);
    return () => document.removeEventListener("keydown", dismiss);
  }, [active]);

  if (values.length === 0) {
    return <p className="chart-empty">{spanish ? "sin dato para esta métrica" : "no data for this metric"}</p>;
  }

  return (
    <>
      <ul className="chart-rows">
        {rows.map(({ id, name, summary: { p10, p50, p90, n }, annual }) => {
          const tooltipId = `${chartId}-${id}`;
          const close = () => setActive((current) => current === id ? null : current);
          return (
            <li
              className="chart-row"
              key={id}
              data-rot={id}
              onPointerEnter={(event) => { if (event.pointerType === "mouse") setActive(id); }}
              onPointerLeave={(event) => { if (!event.currentTarget.contains(document.activeElement)) close(); }}
            >
              <button
                type="button"
                className="chart-reading"
                aria-labelledby={`${tooltipId}-name`}
                aria-describedby={tooltipId}
                onFocus={() => setActive(id)}
                onBlur={close}
                onClick={(event) => { event.currentTarget.focus(); setActive(id); }}
              >
                <span className="chart-reading-header">
                  <span className="chart-rotation">
                    <span className="chart-swatch" style={{ borderTopStyle: ROTATION_STYLE[id].swatch }} aria-hidden />
                    <span id={`${tooltipId}-name`}>{name}</span>
                  </span>
                  <strong>{format(p50)}</strong>
                </span>
                <span className="chart-track" aria-hidden>
                  <span className="chart-gridline" style={{ left: `${position(0)}%` }} />
                  {p10 !== null && p90 !== null && p10 !== p90 ? (
                    <span className="chart-band" style={{
                      left: `${position(p10)}%`,
                      width: `${position(p90) - position(p10)}%`,
                      borderTopStyle: ROTATION_STYLE[id].swatch,
                    }} />
                  ) : null}
                  {annual.map(({ year, value }) => value === null ? null : (
                    <span key={year} className="chart-dot" style={{ left: `${position(value)}%` }} />
                  ))}
                  {p50 !== null ? <span className="chart-median" style={{ left: `${position(p50)}%` }} /> : null}
                </span>
              </button>
              <div className="chart-tooltip" role="tooltip" id={tooltipId} hidden={active !== id}>
                <dl>
                  <div><dt>p10</dt><dd>{format(p10)}</dd></div>
                  <div><dt>{spanish ? "Mediana (p50)" : "Median (p50)"}</dt><dd>{format(p50)}</dd></div>
                  <div><dt>p90</dt><dd>{format(p90)}</dd></div>
                  <div><dt>{spanish ? "Años en la muestra" : "Years in the sample"}</dt><dd>{n}</dd></div>
                </dl>
                {annual.length > 0 ? (
                  <p>{spanish ? "Por año" : "By year"} · {annual.map(({ year, value }) => `${year} · ${format(value)}`).join(" / ")}</p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
      <div className="chart-axis" aria-hidden>
        {ticks.map((value) => (
          <span key={value}>{value > 0 && difference ? "+" : ""}{formatNumber(value, lang, 2)}</span>
        ))}
        <span className="chart-axis-unit">{metricUnit(metric, lang)}</span>
      </div>
    </>
  );
}

function RotationTable({ rows, title, lang, format }: {
  rows: Reading[];
  title: string;
  lang: Lang;
  format: ValueFormat;
}) {
  const spanish = lang === "es";
  return (
    <table className="rotation-table">
      <caption>{title}</caption>
      <thead>
        <tr>
          <th scope="col">{spanish ? "Rotación" : "Rotation"}</th>
          <th scope="col">p10</th>
          <th scope="col">p50</th>
          <th scope="col">p90</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ id, name, summary }) => (
          <tr key={id}>
            <th scope="row">
              {name}
              <small>{spanish ? "Años en la muestra" : "Years in the sample"} · {summary.n}</small>
            </th>
            <td>{format(summary.p10)}</td>
            <td>{format(summary.p50)}</td>
            <td>{format(summary.p90)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ComparisonViewPicker({ view, onChange, lang }: {
  view: ComparisonView;
  onChange: (value: ComparisonView) => void;
  lang: Lang;
}) {
  const spanish = lang === "es";
  return <RadioGroup label={spanish ? "Vista de los datos" : "Data view"} value={view} onChange={onChange}
    className="comparison-picker"
    options={[
      { value: "chart", label: spanish ? "Gráfico" : "Chart" },
      { value: "table", label: spanish ? "Tabla" : "Table" },
    ]}
  />;
}

export function ComparisonResults({ compare, metric, lang, names, view }: {
  compare: CompareResponse;
  metric: MetricId;
  lang: Lang;
  names: Record<string, string>;
  view: ComparisonView;
}) {
  const sectionId = useId();
  const spanish = lang === "es";
  const baseline = rotationName(compare.baseline_rotation_id, lang, names[compare.baseline_rotation_id]);
  const rotations = ROTATION_ORDER.flatMap((id) => {
    const rotation = compare.rotations.find((item) => item.rotation_id === id);
    return rotation ? [rotation] : [];
  });
  const annual = rotations.flatMap((rotation) => rotation.runs.map((run) => ({
    id: rotation.rotation_id,
    year: run.year,
    value: run.metrics[metric],
  })));

  if (rotations.length === 0) {
    return <p className="chart-empty">{spanish ? "sin dato para esta comparación" : "no data for this comparison"}</p>;
  }

  return (
    <div className="comparison-results" data-view={view}>
      {[true, false].map((difference) => {
        const id = `${sectionId}-${difference ? "difference" : "level"}`;
        const title = difference
          ? (spanish ? `Diferencia frente a ${baseline}` : `Difference from ${baseline}`)
          : (spanish ? "Valores modelados por rotación" : "Modeled values by rotation");
        const rows = rotations.map((rotation) => ({
          id: rotation.rotation_id,
          name: rotationName(rotation.rotation_id, lang, names[rotation.rotation_id]),
          summary: (difference ? rotation.delta_vs_baseline : rotation.metrics)[metric],
          annual: difference ? [] : annual.filter((reading) => reading.id === rotation.rotation_id),
        }));
        const format = (value: number | null) => difference ? formatSigned(value, metric, lang) : formatValue(value, metric, lang);

        return view === "table" ? (
          <RotationTable key={id} rows={rows} title={title} lang={lang} format={format} />
        ) : (
          <section key={id} className="chart-panel" aria-labelledby={id}>
            <h2 id={id}>{title}</h2>
            <p className="chart-guide">
              {difference
                ? (spanish ? "Cero marca la referencia. Un valor negativo indica una cifra modelada más baja." : "Zero marks the reference. A negative value indicates a lower modeled figure.")
                : (spanish ? "La escala empieza en cero. Los puntos muestran las cifras de cada año." : "The scale starts at zero. Dots show the figures for each year.")}
            </p>
            <RotationPlot rows={rows} difference={difference} metric={metric} lang={lang} format={format} />
          </section>
        );
      })}
      {view === "table" && annual.length > 0 ? (
        <table className="rotation-table">
          <caption>{spanish ? "Valores modelados por año" : "Modeled values by year"}</caption>
          <thead>
            <tr>
              <th scope="col">{spanish ? "Rotación" : "Rotation"}</th>
              <th scope="col">{spanish ? "Año" : "Year"}</th>
              <th scope="col">{spanish ? "Valor" : "Value"}</th>
            </tr>
          </thead>
          <tbody>
            {annual.map(({ id, year, value }) => (
              <tr key={`${id}-${year}`}>
                <th scope="row">{rotationName(id, lang, names[id])}</th>
                <td>{year}</td>
                <td>{formatValue(value, metric, lang)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}

export function ComparisonSkeleton({ view }: { view: ComparisonView }) {
  return (
    <div className={`comparison-skeleton ${view === "table" ? "comparison-skeleton-table" : ""}`} aria-hidden>
      {[0, 1].map((panel) => (
        <div key={panel} className="chart-skeleton">
          <div className="chart-skeleton-title" />
          {[0, 1, 2].map((row) => <div key={row} className="chart-skeleton-row"><span /><span /></div>)}
        </div>
      ))}
    </div>
  );
}
