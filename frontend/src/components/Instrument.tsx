import { useId, useState, type KeyboardEvent, type ReactNode } from "react";
import { CalendarRange, DropletOff, Droplets, ThermometerSun, type LucideIcon } from "lucide-react";
import { formatNumber, formatValue, metricUnit } from "../lib/format";
import type { Lang, MetricId } from "../lib/types";

export const METRIC_ICON: Record<MetricId | "seasons", LucideIcon> = {
  modeled_water_deficit_mm: DropletOff,
  crop_water_demand_mm: Droplets,
  water_stress_days: ThermometerSun,
  seasons: CalendarRange,
};

export function StatusPill({ tone = "pending", children }: { tone?: "pending" | "ok" | "alert"; children: ReactNode }) {
  return <span className="status-pill" data-tone={tone}>{children}</span>;
}

/** A number set large with its unit set small, the way an instrument face reads. */
export function Figure({ value, metric, lang, unit }: { value: number | null; metric?: MetricId; lang: Lang; unit?: string }) {
  if (value === null) return <span className="figure figure-empty">{formatValue(null, metric ?? "modeled_water_deficit_mm", lang)}</span>;
  return (
    <span className="figure">
      {formatNumber(value, lang)}
      <small>{unit ?? (metric ? metricUnit(metric, lang) : "")}</small>
    </span>
  );
}

export type Stat = {
  id: string;
  label: string;
  icon: LucideIcon;
  value: ReactNode;
  high?: string;
  low?: string;
  note?: string;
  active?: boolean;
};

export function StatGrid({ stats, lang, className = "" }: { stats: Stat[]; lang: Lang; className?: string }) {
  const es = lang === "es";
  return (
    <dl className={`stat-grid ${className}`}>
      {stats.map(({ id, label, icon: Icon, value, high, low, note, active }) => (
        <div key={id} className="stat" data-active={active ? "" : undefined}>
          <dt>
            <span>{label}</span>
            <Icon size={16} strokeWidth={1.6} aria-hidden />
          </dt>
          <dd>
            {value}
            {high !== undefined && low !== undefined ? (
              <span className="stat-range">
                <span>{es ? "Alto" : "High"}</span><b>{high}</b>
                <span>{es ? "Bajo" : "Low"}</span><b>{low}</b>
              </span>
            ) : null}
          </dd>
          {note ? <dd className="stat-note">{note}</dd> : null}
        </div>
      ))}
    </dl>
  );
}

const STOPS = ["--cond-1", "--cond-2", "--cond-3", "--cond-4", "--cond-5"];

/** Condition color for t in [0, 1]: green when low, red when high. */
export function conditionColor(t: number): string {
  const clamped = Math.min(1, Math.max(0, t));
  const scaled = clamped * (STOPS.length - 1);
  const low = Math.floor(scaled);
  const high = Math.min(STOPS.length - 1, low + 1);
  const mix = Math.round((scaled - low) * 100);
  return `color-mix(in oklab, var(${STOPS[low]}) ${100 - mix}%, var(${STOPS[high]}))`;
}

/**
 * Tick scale: a row of thin bars painted on the condition scale, with one marker.
 * Ticks past the marker fade, so the bar reads as "filled up to here".
 */
export function TickScale({ value, min, max, ticks = 56, startLabel, endLabel, label }: {
  value: number | null;
  min: number;
  max: number;
  ticks?: number;
  startLabel?: string;
  endLabel?: string;
  label: string;
}) {
  const span = max - min || 1;
  const t = value === null ? null : Math.min(1, Math.max(0, (value - min) / span));
  const markerIndex = t === null ? -1 : Math.round(t * (ticks - 1));
  return (
    <div className="tick-scale" role="img" aria-label={label}>
      <div className="tick-row" aria-hidden="true">
        {Array.from({ length: ticks }, (_, index) => (
          <i key={index}
            data-past={markerIndex >= 0 && index > markerIndex ? "" : undefined}
            data-marker={index === markerIndex ? "" : undefined}
            style={{ background: index === markerIndex ? undefined : conditionColor(index / (ticks - 1)), animationDelay: `${index * 9}ms` }} />
        ))}
      </div>
      {startLabel || endLabel ? (
        <div className="tick-ends" aria-hidden="true"><span>{startLabel}</span><span>{endLabel}</span></div>
      ) : null}
    </div>
  );
}

type SoilRow = { date: string; value: number | null; status: boolean | null };

/** Stepped soil-water line, colored by stress state, with a hover and keyboard readout. */
export function SoilChart({ rows, lang, height = 168 }: { rows: SoilRow[]; lang: Lang; height?: number }) {
  const es = lang === "es";
  const gradient = useId();
  const [index, setIndex] = useState<number | null>(null);
  const n = rows.length;
  const values = rows.map(({ value }) => value).filter((value): value is number => value !== null);
  const top = Math.max(1, ...values) * 1.12;
  const step = 10 ** Math.floor(Math.log10(top / 3));
  const ceiling = Math.ceil(top / step) * step;
  const W = 1000;
  const x = (i: number) => (i / Math.max(1, n)) * W;
  const y = (value: number) => height - (value / ceiling) * height;
  const tone = (status: boolean | null) => status === true ? "stress" : status === false ? "ok" : "idle";

  const runs: { tone: string; d: string }[] = [];
  let area = "";
  for (let i = 0; i < n; i += 1) {
    const row = rows[i];
    if (row.value === null) continue;
    const prev = rows[i - 1];
    const startsArea = !prev || prev.value === null;
    area += startsArea ? `M${x(i)} ${height} V${y(row.value)} H${x(i + 1)}` : ` V${y(row.value)} H${x(i + 1)}`;
    const next = rows[i + 1];
    if (!next || next.value === null) area += ` V${height} Z `;
    const key = tone(row.status);
    const last = runs.at(-1);
    if (last && !startsArea && last.tone === key) {
      last.d += ` V${y(row.value)} H${x(i + 1)}`;
    } else {
      const from = !startsArea && prev?.value != null ? `M${x(i)} ${y(prev.value)} V${y(row.value)}` : `M${x(i)} ${y(row.value)}`;
      runs.push({ tone: key, d: `${from} H${x(i + 1)}` });
    }
  }

  const monthly = new Intl.DateTimeFormat(es ? "es-CR" : "en-US", { month: "short", timeZone: "UTC" });
  const daily = new Intl.DateTimeFormat(es ? "es-CR" : "en-US", { day: "numeric", month: "short", timeZone: "UTC" });
  const months = rows.flatMap(({ date }, i) => date.endsWith("-01") ? [{ i, label: monthly.format(new Date(date)) }] : []);
  const grid = [ceiling / 3, (2 * ceiling) / 3, ceiling];
  const active = index !== null ? rows[index] : null;

  function pick(clientX: number, box: DOMRect) {
    const ratio = (clientX - box.left) / box.width;
    setIndex(Math.min(n - 1, Math.max(0, Math.floor(ratio * n))));
  }

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    const moves: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1, PageUp: 7, PageDown: -7 };
    if (event.key === "Escape") { setIndex(null); return; }
    if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      setIndex(event.key === "Home" ? 0 : n - 1);
      return;
    }
    const move = moves[event.key];
    if (move === undefined) return;
    event.preventDefault();
    setIndex((current) => Math.min(n - 1, Math.max(0, (current ?? 0) + move)));
  }

  const status = active?.status === true ? (es ? "Día con estrés hídrico" : "Water stress day")
    : active?.status === false ? (es ? "Sin estrés hídrico" : "No water stress")
    : (es ? "Sin cultivo activo" : "No active crop");

  return (
    <div className="soil-chart" style={{ height: height + 26 }}>
      <div className="soil-grid" aria-hidden="true" style={{ height }}>
        {grid.map((value) => (
          <span key={value} style={{ bottom: `${(value / ceiling) * 100}%` }}><em>{formatNumber(value, lang, 0)}</em></span>
        ))}
      </div>
      <div
        className="soil-plot"
        style={{ height }}
        tabIndex={0}
        role="img"
        aria-label={es ? "Agua almacenada en el suelo por día. Flechas para recorrer los días." : "Water stored in the soil by day. Use arrow keys to step through days."}
        onPointerMove={(event) => pick(event.clientX, event.currentTarget.getBoundingClientRect())}
        onPointerLeave={() => setIndex(null)}
        onKeyDown={onKey}
        onBlur={() => setIndex(null)}
      >
        <svg viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id={gradient} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor="var(--cond-1)" stopOpacity="0.2" />
              <stop offset="1" stopColor="var(--cond-1)" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={area} fill={`url(#${gradient})`} />
          {index !== null ? <rect className="soil-band" x={x(Math.max(0, index - 3))} width={x(7)} y={0} height={height} /> : null}
          {runs.map((run, i) => <path key={i} className="soil-line" data-tone={run.tone} d={run.d} />)}
        </svg>
        {active && active.value !== null ? (
          <div className="soil-tip" style={{ left: `${((index! + 0.5) / n) * 100}%`, bottom: `${(active.value / ceiling) * 100}%` }}>
            <strong>{formatValue(active.value, "modeled_water_deficit_mm", lang)}</strong>
            <span>{daily.format(new Date(active.date))} · {status}</span>
          </div>
        ) : null}
      </div>
      <div className="soil-months" aria-hidden="true">
        {months.map(({ i, label }) => <span key={i} style={{ left: `${(i / n) * 100}%` }}>{label}</span>)}
      </div>
    </div>
  );
}
