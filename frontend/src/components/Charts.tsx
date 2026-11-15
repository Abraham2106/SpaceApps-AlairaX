import type { CompareResponse, Lang, MetricId, RotationId } from "../lib/types";
import { formatSigned, formatValue } from "../lib/format";
import { ROTATION_ORDER, ROTATION_STYLE, metricNoun, rotationName } from "../lib/plain";

function extent(compare: CompareResponse, metric: MetricId): number {
  let max = 1;
  for (const rotation of compare.rotations) {
    const summary = rotation.metrics[metric];
    for (const value of [summary.p10, summary.p50, summary.p90]) {
      if (value !== null) max = Math.max(max, value);
    }
    for (const run of rotation.runs) {
      const value = run.metrics[metric];
      if (value !== null) max = Math.max(max, value);
    }
  }
  return max * 1.08;
}

export function LevelChart({ compare, metric, lang, names }: { compare: CompareResponse; metric: MetricId; lang: Lang; names: Record<string, string> }) {
  const width = 640;
  const height = 210;
  const left = 168;
  const right = 16;
  const max = extent(compare, metric);
  const xOf = (value: number) => left + ((width - left - right) * value) / max;
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="level-title level-desc">
        <title id="level-title">{lang === "es" ? "Nivel modelado, escala desde cero" : "Modeled level, scale from zero"}</title>
        <desc id="level-desc">
          {lang === "es"
            ? "Cada fila es una rotación. La banda va de p10 a p90. La raya es p50. Cada punto es un año análogo."
            : "Each row is a rotation. The band runs from p10 to p90. The tick is p50. Each dot is an analog year."}
        </desc>
        {[0, 0.5, 1].map((step) => {
          const value = max * step;
          const x = xOf(value);
          return (
            <g key={step}>
              <line x1={x} x2={x} y1={18} y2={height - 16} stroke="currentColor" opacity="0.15" />
              <text x={x} y={height - 2} textAnchor="middle" fill="currentColor" fontSize="11">
                {Math.round(value)}
              </text>
            </g>
          );
        })}
        {ROTATION_ORDER.map((id, index) => {
          const rotation = compare.rotations.find((item) => item.rotation_id === id);
          const y = 42 + index * 52;
          if (!rotation) return null;
          const summary = rotation.metrics[metric];
          const style = ROTATION_STYLE[id];
          return (
            <g key={id}>
              <text x={8} y={y + 4} fill="currentColor" fontSize="13">
                {rotationName(id, lang, names[id])}
              </text>
              {summary.p10 !== null && summary.p90 !== null ? (
                <line x1={xOf(summary.p10)} x2={xOf(summary.p90)} y1={y} y2={y} stroke={style.color} strokeWidth="8" strokeDasharray={style.dash === "none" ? undefined : style.dash} />
              ) : null}
              {summary.p50 !== null ? <line x1={xOf(summary.p50)} x2={xOf(summary.p50)} y1={y - 10} y2={y + 10} stroke="currentColor" strokeWidth="2" /> : null}
              {rotation.runs.map((run) => {
                const value = run.metrics[metric];
                if (value === null) return null;
                return <circle key={run.year} cx={xOf(value)} cy={y} r="4" fill={style.color} className="rot-dot" strokeWidth="1" />;
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function DeltaChart({ compare, metric, lang, names }: { compare: CompareResponse; metric: MetricId; lang: Lang; names: Record<string, string> }) {
  const width = 640;
  const height = 180;
  const left = 168;
  let span = 1;
  for (const rotation of compare.rotations) {
    const summary = rotation.delta_vs_baseline[metric];
    for (const value of [summary.p10, summary.p50, summary.p90]) {
      if (value !== null) span = Math.max(span, Math.abs(value));
    }
  }
  span *= 1.25;
  const mid = left + (width - left - 16) / 2;
  const xOf = (value: number) => mid + ((width - left - 16) / 2) * (value / span);
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="delta-title delta-desc">
        <title id="delta-title">{lang === "es" ? "Delta contra arroz y melón" : "Delta against rice and melon"}</title>
        <desc id="delta-desc">
          {lang === "es"
            ? "Cero es la referencia. La banda es p10 a p90 del delta que ya trae el contrato. Un valor negativo es un número modelado más bajo, no un ahorro."
            : "Zero is the reference. The band is the contract delta from p10 to p90. A negative value is a lower modeled number, not savings."}
        </desc>
        <line x1={mid} x2={mid} y1={16} y2={height - 22} stroke="currentColor" />
        {[-span, 0, span].map((value) => (
          <text key={value} x={xOf(value)} y={height - 4} textAnchor="middle" fill="currentColor" fontSize="11">
            {value > 0 ? `+${Math.round(value)}` : Math.round(value)}
          </text>
        ))}
        {ROTATION_ORDER.map((id, index) => {
          const rotation = compare.rotations.find((item) => item.rotation_id === id);
          const y = 36 + index * 44;
          if (!rotation) return null;
          const summary = rotation.delta_vs_baseline[metric];
          const style = ROTATION_STYLE[id];
          const flat = summary.p10 !== null && summary.p90 !== null && summary.p10 === summary.p90;
          return (
            <g key={id}>
              <text x={8} y={y + 4} fill="currentColor" fontSize="13">{rotationName(id, lang, names[id])}</text>
              {summary.p10 !== null && summary.p90 !== null && !flat ? (
                <line x1={xOf(summary.p10)} x2={xOf(summary.p90)} y1={y} y2={y} stroke={style.color} strokeWidth="8" />
              ) : null}
              {summary.p50 !== null ? (
                <>
                  <circle cx={xOf(summary.p50)} cy={y} r="5" fill={style.color} />
                  <text x={xOf(summary.p50) + 10} y={y + 4} fill="currentColor" fontSize="12">
                    {formatSigned(summary.p50, metric, lang)}
                  </text>
                </>
              ) : (
                <text x={left} y={y + 4} fill="currentColor" fontSize="12">{lang === "es" ? "sin dato" : "no data"}</text>
              )}
            </g>
          );
        })}
      </svg>
      <p className="faint">
        {metricNoun(metric, lang)}.{" "}
        {lang === "es"
          ? "Escala simétrica alrededor de cero. Si p10 y p90 coinciden, no hay banda: los años análogos dieron el mismo delta."
          : "Symmetric scale around zero. If p10 and p90 match, there is no band: the analog years produced the same delta."}
      </p>
    </div>
  );
}

export function ComparisonTable({ compare, metric, lang, names }: { compare: CompareResponse; metric: MetricId; lang: Lang; names: Record<string, string> }) {
  return (
    <table>
      <caption>{lang === "es" ? "Tabla de la comparación" : "Comparison table"}</caption>
      <thead>
        <tr>
          <th>{lang === "es" ? "Rotación" : "Rotation"}</th>
          <th>p10</th>
          <th>p50</th>
          <th>p90</th>
          <th>n</th>
          <th>{lang === "es" ? "Delta p50" : "Delta p50"}</th>
        </tr>
      </thead>
      <tbody>
        {ROTATION_ORDER.map((id) => {
          const rotation = compare.rotations.find((item) => item.rotation_id === id);
          if (!rotation) return null;
          const summary = rotation.metrics[metric];
          const delta = rotation.delta_vs_baseline[metric];
          return (
            <tr key={id}>
              <th scope="row">{rotationName(id as RotationId, lang, names[id])}</th>
              <td>{formatValue(summary.p10, metric, lang)}</td>
              <td>{formatValue(summary.p50, metric, lang)}</td>
              <td>{formatValue(summary.p90, metric, lang)}</td>
              <td>{summary.n}</td>
              <td>{formatSigned(delta.p50, metric, lang)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
