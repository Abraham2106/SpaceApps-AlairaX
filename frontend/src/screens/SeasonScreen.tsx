import { translate } from "../lib/i18n";
import { comparisonError } from "../lib/api";
import { useInstrument } from "../store";
import { useComparison } from "../data/queries";
import { formatValue } from "../lib/format";
import { ROTATION_ORDER, readingMetric, rotationName } from "../lib/plain";
import { QueryState } from "../components/QueryState";
import { comparisonYears, hasDailyBalance, SEASON_MONTHS } from "../lib/season";

const DATES = ["windowStart", "rice", "cowpeaSorghum", "windowEnd", "melon"] as const;

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
  const years = comparisonYears(compare);
  const activeA = yearA !== null && years.includes(yearA) ? yearA : years[0];
  const activeB = yearB !== null && years.includes(yearB) ? yearB : years.at(-1);

  return (
    <div className="screen">
      <article className="detail-page">
        <header className="detail-header">
          <h1>{translate(lang, "common.season")}</h1>
          <p>{translate(lang, "season.referenceDatesYearlyFiguresFrom")}</p>
        </header>
        <div className="detail-layout">
          <section className="detail-panel" aria-labelledby="season-calendar">
            <h2 id="season-calendar">{translate(lang, "season.provisionalCalendar")}</h2>
            <div className="detail-notice">
              <code>verified: false</code>
              <p>{translate(lang, "season.documentedDatesAwaitingValidationWith")}</p>
            </div>
            <div className="season-months" aria-hidden="true">
              {SEASON_MONTHS.map(([, month]) => <span key={month}>{translate(lang, month)}</span>)}
              <span className="season-window" />
            </div>
            <ol className="season-events">
              {DATES.map((event) => (
                <li key={event}>
                  <span className="season-date">{translate(lang, `calendar.${event}Date`)}</span>
                  <div>
                    <h3>{translate(lang, `calendar.${event}`)}</h3>
                    <p>{translate(lang, `calendar.${event}Detail`)}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
          <section className="detail-panel" aria-labelledby="season-years">
            <h2 id="season-years">{translate(lang, "common.compareYears")}</h2>
            <p className="detail-lead">{translate(lang, "season.fullCycleFiguresYearsSimilar")}</p>
            <QueryState pending={comparison.isPending} error={comparison.isError} onRetry={() => comparison.refetch()} lang={lang} />
            {loaded && !compare ? <p className="warn" role="alert">{comparisonError(loaded, lang)}</p> : null}
            {compare && !hasDailyBalance(compare) ? (
              <div className="detail-notice">
                <strong>{translate(lang, "season.dailyBalanceNoData")}</strong>
                <p>{translate(lang, "season.tableListsAvailableFiguresCycle")}</p>
              </div>
            ) : null}
            {compare && (activeA === undefined || activeB === undefined) ? (
              <p className="muted">{translate(lang, "season.yearsSampleNoData")}</p>
            ) : null}
            {compare && activeA !== undefined && activeB !== undefined ? (
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
                      const runs = compare.rotations.find((rotation) => rotation.rotation_id === id)?.runs ?? [];
                      return (
                        <tr key={id}>
                          <th scope="row">{rotationName(id, lang, names[id])}</th>
                          <td>{formatValue(runs.find(({ year }) => year === activeA)?.metrics[metric] ?? null, metric, lang)}</td>
                          <td>{formatValue(runs.find(({ year }) => year === activeB)?.metrics[metric] ?? null, metric, lang)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </>
            ) : null}
            <p className="detail-footnote">{translate(lang, "season.monitoring2026OngoingComparisonUses")}</p>
          </section>
        </div>
      </article>
    </div>
  );
}
