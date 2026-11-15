import { translate } from "../lib/i18n";
import { comparisonError } from "../lib/api";
import { useInstrument } from "../store";
import { useComparison } from "../data/queries";
import { formatValue } from "../lib/format";
import { ROTATION_ORDER, readingMetric, rotationName } from "../lib/plain";
import { QueryState } from "../components/QueryState";
import { SoilChart } from "../components/Instrument";
import { useRecentSeasons } from "../data/recent";
import type { MetricId, RotationId } from "../lib/types";



export function SeasonScreen() {
  const lang = useInstrument((state) => state.lang);
  const metric = useInstrument((state) => state.metric);
  const yearA = useInstrument((state) => state.yearA);
  const yearB = useInstrument((state) => state.yearB);
  const setYears = useInstrument((state) => state.setYears);
  const comparison = useComparison();
  const loaded = comparison.data;
  const compare = loaded?.compare;
  const names = Object.fromEntries((loaded?.catalog.rotations ?? []).map((item) => [item.id, item.name]));
  const recent = useRecentSeasons();
  const years = recent.data?.seasons.map(({ year }) => year).sort((a, b) => b - a) ?? [];
  const activeA = yearA !== null && years.includes(yearA) ? yearA : years[0];
  const activeB = yearB !== null && years.includes(yearB) ? yearB : years[1] ?? years[0];
  const seasonA = recent.data?.seasons.find(({ year }) => year === activeA);
  const seasonB = recent.data?.seasons.find(({ year }) => year === activeB);
  const dates = seasonA?.runs[0]?.daily_balance.map(({ date }) => date) ?? [];
  const baselineId = compare?.baseline_rotation_id ?? "rice_melon";
  const baselineRows = (seasonA?.runs.find(({ rotation_id }) => rotation_id === baselineId)?.daily_balance ?? [])
    .map((row) => ({ date: row.date, value: row.soil_water_storage_mm, status: row.water_stress }));
  const cutoff = [seasonA?.end.slice(5), seasonB?.end.slice(5)].filter((value): value is string => Boolean(value)).sort()[0] ?? "12-31";
  function total(season: typeof seasonA, rotation: RotationId, metric: MetricId): number | null {
    const days = season?.runs.find(({ rotation_id }) => rotation_id === rotation)?.daily_balance
      .filter(({ date }) => date.slice(5) <= cutoff);
    if (!days?.length || days.some((day) => day.crop_water_demand_mm === null || day.modeled_water_deficit_mm === null)) return null;
    if (metric === "water_stress_days") return days.filter(({ water_stress }) => water_stress === true).length;
    return days.reduce((sum, day) => sum + (day[metric] ?? 0), 0);
  }
  const dateFormat = new Intl.DateTimeFormat(lang === "es" ? "es-CR" : "en-US", {
    dateStyle: "medium", timeZone: "UTC",
  });

  return (
    <div className="screen texture-waves">
      <article className="detail-page">
        <header className="detail-header">
          <h1>{translate(lang, "common.season")}</h1>
          <p>{translate(lang, "season.referenceDatesYearlyFiguresFrom")}</p>
        </header>
        <div className="detail-layout">
          {dates.length ? (
            <section className="detail-panel" aria-labelledby="season-calendar">
              <h2 id="season-calendar">{translate(lang, "mapSeasonPlayer.modeledSeason")}</h2>
              <p className="detail-lead">{dateFormat.formatRange(new Date(dates[0]), new Date(dates[dates.length - 1]))}</p>
              {baselineRows.some(({ value }) => value !== null) ? (
                <>
                  <h3 className="season-chart-title">{lang === "es" ? "Agua en el suelo" : "Water in the soil"} · {rotationName(baselineId, lang, names[baselineId])}</h3>
                  <SoilChart rows={baselineRows} lang={lang} height={150} />
                </>
              ) : null}
            </section>
          ) : null}
          <section className="detail-panel" aria-labelledby="season-years">
            <h2 id="season-years">{translate(lang, "common.compareYears")}</h2>
            <p className="detail-lead">{lang === "es" ? "Compará las tres rotaciones con el clima de cada año." : "Compare the three rotations using each year’s weather."}</p>
            <QueryState pending={recent.isPending} error={recent.isError} onRetry={() => recent.refetch()} lang={lang} />
            {loaded && !compare ? <p className="warn" role="alert">{comparisonError(loaded, lang)}</p> : null}
            {seasonA && seasonB && activeA !== undefined && activeB !== undefined ? (
              <>
                <div className="season-year-fields">
                  <div className="detail-field">
                    <label htmlFor="season-year-a">{translate(lang, "common.yearA")}</label>
                    <select id="season-year-a" value={activeA} onChange={(event) => setYears(Number(event.target.value), activeB)}>
                      {years.map((year) => <option value={year} key={year}>{year}</option>)}
                    </select>
                  </div>
                  <div className="detail-field">
                    <label htmlFor="season-year-b">{translate(lang, "common.yearB")}</label>
                    <select id="season-year-b" value={activeB} onChange={(event) => setYears(activeA, Number(event.target.value))}>
                      {years.map((year) => <option value={year} key={year}>{year}</option>)}
                    </select>
                  </div>
                </div>
                <p className="detail-footnote">{lang === "es" ? "Periodo comparado en ambos años" : "Period compared in both years"} · {dateFormat.formatRange(new Date(`${activeA}-01-01`), new Date(`${activeA}-${cutoff}`))}</p>
                <table className="detail-table">
                  <caption>{readingMetric(metric, lang)}</caption>
                  <thead>
                    <tr>
                      <th scope="col">{translate(lang, "common.rotation")}</th>
                      <th scope="col">A · {activeA}</th>
                      <th scope="col">B · {activeB}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ROTATION_ORDER.map((id) => {
                      return (
                        <tr key={id}>
                          <th scope="row">{rotationName(id, lang, names[id])}</th>
                          <td>{formatValue(total(seasonA, id, metric), metric, lang)}</td>
                          <td>{formatValue(total(seasonB, id, metric), metric, lang)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </>
            ) : null}

          </section>
        </div>
      </article>
    </div>
  );
}
