import { useState } from "react";
import { useRecentSeasons } from "../data/recent";
import { QueryState } from "./QueryState";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Figure, SoilChart, StatusPill, conditionColor } from "./Instrument";
import { formatValue } from "../lib/format";
import { ROTATION_ORDER, readingMetric, rotationName } from "../lib/plain";
import { METRIC_IDS, type CompareResponse, type Lang, type MetricId, type RotationId } from "../lib/types";

const DAY = 86_400_000;

function periodLabel(start: string, end: string, lang: Lang) {
  return new Intl.DateTimeFormat(lang === "es" ? "es-CR" : "en-US", {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  }).formatRange(new Date(start), new Date(end));
}

function YearSelect({ years, year, onChange, label }: { years: number[]; year: number | undefined; onChange: (year: number) => void; label: string }) {
  if (years.length === 0) return null;
  return (
    <select className="card-select" aria-label={label} value={year} onChange={(event) => onChange(Number(event.target.value))}>
      {years.map((value) => <option key={value}>{value}</option>)}
    </select>
  );
}

export function SoilStorageCard({ compare, lang }: { compare: CompareResponse; lang: Lang }) {
  const es = lang === "es";
  const [pickedYear, setPickedYear] = useState<number>();
  const [pickedRotation, setPickedRotation] = useState(compare.baseline_rotation_id);
  const recent = useRecentSeasons();
  const years = recent.data?.seasons.map(({ year }) => year).sort((a, b) => b - a) ?? [];
  const year = pickedYear !== undefined && years.includes(pickedYear) ? pickedYear : years[0];
  const season = recent.data?.seasons.find((item) => item.year === year);
  const rows = season?.runs.find(({ rotation_id }) => rotation_id === pickedRotation)?.daily_balance ?? [];
  const daily = rows.map((row) => ({ date: row.date, value: row.soil_water_storage_mm, status: row.water_stress }));
  const canDraw = daily.some(({ value }) => value !== null);
  const stressDays = daily.filter(({ status }) => status === true).length;

  return (
    <Card className="insight-card storage-card">
      <CardHeader>
        <CardTitle>{es ? "Agua en el suelo" : "Water in the soil"}</CardTitle>
        <div className="card-tools">
          <select className="card-select" aria-label={es ? "Rotación de agua en el suelo" : "Soil water rotation"} value={pickedRotation}
            onChange={(event) => setPickedRotation(event.target.value as typeof pickedRotation)}>
            {compare.rotations.map(({ rotation_id }) => <option key={rotation_id} value={rotation_id}>{rotationName(rotation_id, lang)}</option>)}
          </select>
          <YearSelect years={years} year={year} onChange={setPickedYear} label={es ? "Año de agua en el suelo" : "Soil water year"} />
        </div>
      </CardHeader>
      <CardContent>
        <QueryState pending={recent.isPending} error={recent.isError} onRetry={() => recent.refetch()} lang={lang} />
        {season && <p className="insight-caption">{periodLabel(season.start, season.end, lang)}</p>}
        {canDraw ? <SoilChart rows={daily} lang={lang} /> : null}
        <p className="insight-caption soil-key">
          <span><i data-tone="ok" />{es ? "Sin estrés" : "No stress"}</span>
          <span><i data-tone="stress" />{es ? `Estrés hídrico · ${stressDays} días` : `Water stress · ${stressDays} days`}</span>
          <span><i data-tone="idle" />{es ? "Sin cultivo" : "No crop"}</span>
          <span className="soil-unit">{es ? "mm almacenados" : "Stored mm"}</span>
        </p>
      </CardContent>
    </Card>
  );
}

const ROTATION_INDEX = { rice_melon: 0, rice_legume: 1, rice_sorghum: 2 } as const;

export function WeeklyHeatmap({ compare, lang }: { compare: CompareResponse; lang: Lang }) {
  const es = lang === "es";
  const [chosenYear, setChosenYear] = useState<number>();
  const [chosenWeek, setChosenWeek] = useState(0);
  const recent = useRecentSeasons();
  const years = recent.data?.seasons.map(({ year }) => year).sort((a, b) => b - a) ?? [];
  const year = chosenYear !== undefined && years.includes(chosenYear) ? chosenYear : years[0];
  const season = recent.data?.seasons.find((item) => item.year === year);
  const runs = compare.rotations.map(({ rotation_id }) => ({
    id: rotation_id,
    rows: season?.runs.find((run) => run.rotation_id === rotation_id)?.daily_balance ?? [],
  }));
  const dates = runs.flatMap(({ rows }) => rows.map(({ date }) => date)).sort();
  const first = dates[0];
  const last = dates.at(-1);
  const count = first && last ? Math.floor((Date.parse(last) - Date.parse(first)) / (7 * DAY)) + 1 : 0;
  const rangeStart = first ? Date.parse(first) : 0;
  const datesByWeek = Array.from({ length: count }, (_, index) => rangeStart + index * 7 * DAY);
  const values = runs.map(({ id, rows }) => {
    const byDate = new Map(rows.map((row) => [Date.parse(row.date), row.modeled_water_deficit_mm]));
    return { id, totals: datesByWeek.map((start) => {
      let total = 0;
      for (let day = start; last && day <= Math.min(Date.parse(last), start + 6 * DAY); day += DAY) {
        const value = byDate.get(day);
        if (value == null) return null;
        total += value;
      }
      return total;
    }) };
  });
  const limit = Math.max(0, ...values.flatMap(({ totals }) => totals.map((value) => value ?? 0)));
  const week = Math.min(chosenWeek, Math.max(0, count - 1));
  const dateLabel = new Intl.DateTimeFormat(es ? "es-CR" : "en-US", { day: "numeric", month: "short", timeZone: "UTC" });
  const cropNames = es ? ["Melón", "Leguminosa", "Sorgo"] : ["Melon", "Legume", "Sorghum"];

  return (
    <Card className="insight-card heat-card">
      <CardHeader>
        <CardTitle>{es ? "Agua faltante por semana" : "Weekly water shortfall"}</CardTitle>
        <YearSelect years={years} year={year} label={es ? "Año del mapa de calor" : "Heatmap year"}
          onChange={(value) => { setChosenYear(value); setChosenWeek(0); }} />
      </CardHeader>
      <CardContent>
        <QueryState pending={recent.isPending} error={recent.isError} onRetry={() => recent.refetch()} lang={lang} />
        {season && <p className="insight-caption">{periodLabel(season.start, season.end, lang)}</p>}
        {count > 0 ? (
          <>
            <div className="heat-grid">
              {values.map(({ id, totals }, index) => (
                <div key={id} className="heat-row" data-rot={id}>
                  <span><i />{cropNames[ROTATION_INDEX[id]] ?? index + 1}</span>
                  <div className="heat-cells" aria-hidden="true">
                    {totals.map((value, column) => (
                      <span key={column} className={column === week ? "heat-active" : undefined}
                        style={value === null ? undefined : { background: value === 0 ? "var(--heat-zero)" : conditionColor(value / (limit || 1)) }}
                        data-level={value === null ? "empty" : undefined}
                        onPointerEnter={() => setChosenWeek(column)} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <label className="heat-week">
              <span>{es ? "Semana del" : "Week of"} <strong>{dateLabel.format(datesByWeek[week])}</strong></span>
              <input type="range" min={0} max={count - 1} value={week} aria-valuetext={dateLabel.format(datesByWeek[week])}
                onChange={(event) => setChosenWeek(Number(event.target.value))} />
            </label>
            <dl className="heat-values">
              {values.map(({ id, totals }) => (
                <div key={id} data-rot={id}><dt><i />{cropNames[ROTATION_INDEX[id]]}</dt>
                  <dd>{formatValue(totals[week] ?? null, "modeled_water_deficit_mm", lang)}</dd></div>
              ))}
            </dl>
            <p className="insight-caption heat-key">
              <span className="heat-scale" aria-hidden="true">{[0, 0.25, 0.5, 0.75, 1].map((t) => <i key={t} style={{ background: conditionColor(t) }} />)}</span>
              {es ? `0–${Math.ceil(limit)} mm por semana · gris: sin dato` : `0–${Math.ceil(limit)} mm per week · gray: no data`}
            </p>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

/** Rotations ranked on the chosen metric. Lower is better for every metric this model reports. */
export function RankCard({ compare, metric, lang }: { compare: CompareResponse; metric: MetricId; lang: Lang }) {
  const es = lang === "es";
  const rows = ROTATION_ORDER.flatMap((id) => {
    const rotation = compare.rotations.find((item) => item.rotation_id === id);
    return rotation ? [{ id, amount: rotation.metrics[metric].p50 }] : [];
  }).sort((a, b) => (a.amount ?? Infinity) - (b.amount ?? Infinity));
  const top = Math.max(1, ...rows.map(({ amount }) => amount ?? 0));
  const ticks = 40;

  return (
    <Card className="insight-card rank-card">
      <CardHeader><CardTitle>{readingMetric(metric, lang)}</CardTitle></CardHeader>
      <CardContent>
        <ol className="rank-list">
          {rows.map(({ id, amount }, index) => {
            const filled = amount === null ? 0 : Math.round((amount / top) * ticks);
            return (
              <li key={id} data-rot={id}>
                <div className="rank-head">
                  <span className="rank-name"><i />{rotationName(id, lang)}</span>
                  {index === 0 && amount !== null ? <StatusPill tone="ok">{es ? "Menor" : "Lowest"}</StatusPill> : null}
                  <Figure value={amount} metric={metric} lang={lang} />
                </div>
                <div className="rank-ticks" aria-hidden="true">
                  {Array.from({ length: ticks }, (_, tick) => <i key={tick} data-on={tick < filled ? "" : undefined} />)}
                </div>
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}

/** Every metric side by side. Within a column, green marks the lowest of the three and red the highest. */
export function ProfileCard({ compare, lang }: { compare: CompareResponse; lang: Lang }) {
  const es = lang === "es";
  const heads = es ? ["Agua faltante", "Agua necesaria", "Días de estrés"] : ["Shortfall", "Water need", "Stress days"];
  const rotations = ROTATION_ORDER.flatMap((id) => {
    const rotation = compare.rotations.find((item) => item.rotation_id === id);
    return rotation ? [rotation] : [];
  });
  const rankOf = (metric: MetricId, id: RotationId) => {
    const sorted = rotations.map((rotation) => rotation.metrics[metric].p50).filter((value): value is number => value !== null).sort((a, b) => a - b);
    const value = rotations.find((rotation) => rotation.rotation_id === id)?.metrics[metric].p50 ?? null;
    if (value === null || sorted.length < 2) return null;
    return sorted.indexOf(value) / (sorted.length - 1);
  };

  return (
    <Card className="insight-card profile-card">
      <CardHeader><CardTitle>{es ? "Perfil de las rotaciones" : "Rotation profiles"}</CardTitle></CardHeader>
      <CardContent>
        <table className="profile-table">
          <thead>
            <tr>
              <th scope="col"><span className="sr-only">{es ? "Rotación" : "Rotation"}</span></th>
              {heads.map((head) => <th key={head} scope="col">{head}</th>)}
            </tr>
          </thead>
          <tbody>
            {rotations.map((rotation) => (
              <tr key={rotation.rotation_id} data-rot={rotation.rotation_id}>
                <th scope="row" title={rotationName(rotation.rotation_id, lang)}><i />{(es ? ["Melón", "Leguminosa", "Sorgo"] : ["Melon", "Legume", "Sorghum"])[ROTATION_INDEX[rotation.rotation_id]]}</th>
                {METRIC_IDS.map((metric) => {
                  const rank = rankOf(metric, rotation.rotation_id);
                  return (
                    <td key={metric}>
                      {rank !== null ? <i className="profile-dot" style={{ background: conditionColor(rank) }} aria-hidden="true" /> : null}
                      {formatValue(rotation.metrics[metric].p50, metric, lang)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="insight-caption">{es ? "En cada columna, verde marca el menor de las tres y rojo el mayor. Menos es mejor en las tres medidas." : "In each column, green marks the lowest of the three and red the highest. Lower is better on all three."}</p>
      </CardContent>
    </Card>
  );
}

export function RotationInsights({ compare, metric, lang }: { compare: CompareResponse; metric: MetricId; lang: Lang }) {
  return (
    <div className="rotation-insights">
      <RankCard compare={compare} metric={metric} lang={lang} />
      <ProfileCard compare={compare} lang={lang} />
      <SoilStorageCard compare={compare} lang={lang} />
      <WeeklyHeatmap compare={compare} lang={lang} />
    </div>
  );
}
