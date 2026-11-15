import { useInstrument } from "../store";
import { useComparison } from "../data/queries";
import { formatValue } from "../lib/format";
import { ROTATION_ORDER, readingMetric, rotationName } from "../lib/plain";
import { QueryState } from "../components/QueryState";

const MONTHS = [
  ["Abr", "Apr"], ["May", "May"], ["Jun", "Jun"],
  ["Jul", "Jul"], ["Ago", "Aug"], ["Sep", "Sep"],
  ["Oct", "Oct"], ["Nov", "Nov"], ["Dic", "Dec"],
];

const DATES = [
  {
    date: ["1 abr", "1 Apr"],
    title: ["Abre la ventana de comparación", "Comparison window opens"],
    description: ["Desde esta fecha se toma el clima para buscar años parecidos.", "Climate from this date is used to find similar years."],
  },
  {
    date: ["15 may", "15 May"],
    title: ["Siembra de referencia del arroz", "Reference sowing for rice"],
    description: ["Arroz de secano. Las cuatro etapas duran 30, 30, 60 y 30 días según la tabla 11 de FAO-56.", "Upland rice. The four stages last 30, 30, 60, and 30 days according to FAO-56 Table 11."],
  },
  {
    date: ["15 oct", "15 Oct"],
    title: ["Siembra de referencia del caupí o sorgo", "Reference sowing for cowpea or sorghum"],
    description: ["La rotación indica sorgo forrajero. El archivo de cultivos usa parámetros de sorgo de grano.", "The rotation specifies forage sorghum. The crop file uses grain-sorghum parameters."],
  },
  {
    date: ["31 oct", "31 Oct"],
    title: ["Cierra la ventana de comparación", "Comparison window closes"],
    description: ["Último día del periodo usado para buscar años parecidos.", "Last day of the period used to find similar years."],
  },
  {
    date: ["1 dic", "1 Dec"],
    title: ["Siembra de referencia del melón", "Reference sowing for melon"],
    description: ["El archivo solo asigna riego al melón. Su ciclo continúa el año siguiente.", "The file assigns irrigation only to melon. Its cycle continues into the following year."],
  },
];

export function SeasonScreen() {
  const lang = useInstrument((state) => state.lang);
  const spanish = lang === "es";
  const label = spanish ? 0 : 1;
  const metric = useInstrument((state) => state.metric);
  const yearA = useInstrument((state) => state.yearA);
  const yearB = useInstrument((state) => state.yearB);
  const setYears = useInstrument((state) => state.setYears);
  const comparison = useComparison();
  const loaded = comparison.data;
  const compare = loaded?.compare;
  const names = Object.fromEntries((loaded?.catalog.rotations ?? []).map((item) => [item.id, item.name]));
  const years = compare?.analog_years.map(({ year }) => year).filter((year) => year !== 2026) ?? [];
  const activeA = yearA !== null && years.includes(yearA) ? yearA : years[0];
  const activeB = yearB !== null && years.includes(yearB) ? yearB : years.at(-1);
  const hasDailyBalance = compare?.rotations.some((rotation) => rotation.runs.some((run) => run.daily_balance.length > 0));

  return (
    <div className="screen">
      <article className="detail-page">
        <header className="detail-header">
          <h1>{spanish ? "Temporada" : "Season"}</h1>
          <p>{spanish ? "Fechas de referencia y cifras por año del archivo de simulación." : "Reference dates and yearly figures from the simulation file."}</p>
        </header>
        <div className="detail-layout">
          <section className="detail-panel" aria-labelledby="season-calendar">
            <h2 id="season-calendar">{spanish ? "Calendario provisional" : "Provisional calendar"}</h2>
            <div className="detail-notice">
              <code>verified: false</code>
              <p>{spanish ? "Fechas documentadas, pendientes de validar con productores." : "Documented dates awaiting validation with producers."}</p>
            </div>
            <div className="season-months" aria-hidden="true">
              {MONTHS.map((month) => <span key={month[0]}>{month[label]}</span>)}
              <span className="season-window" />
            </div>
            <ol className="season-events">
              {DATES.map(({ date, title, description }) => (
                <li key={date[0]}>
                  <span className="season-date">{date[label]}</span>
                  <div>
                    <h3>{title[label]}</h3>
                    <p>{description[label]}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
          <section className="detail-panel" aria-labelledby="season-years">
            <h2 id="season-years">{spanish ? "Comparar años" : "Compare years"}</h2>
            <p className="detail-lead">{spanish ? "Cifras del ciclo completo para años parecidos al escenario." : "Full-cycle figures for years similar to the scenario."}</p>
            <QueryState pending={comparison.isPending} error={comparison.isError} onRetry={() => comparison.refetch()} lang={lang} />
            {loaded && !compare ? <p className="warn" role="alert">{loaded.httpDetail}</p> : null}
            {compare && !hasDailyBalance ? (
              <div className="detail-notice">
                <strong>{spanish ? "Balance diario: sin dato" : "Daily balance: no data"}</strong>
                <p>{spanish ? "La tabla reúne las cifras disponibles para el ciclo." : "The table lists the available figures for the cycle."}</p>
              </div>
            ) : null}
            {compare && (activeA === undefined || activeB === undefined) ? (
              <p className="muted">{spanish ? "Años en la muestra: sin dato." : "Years in the sample: no data."}</p>
            ) : null}
            {compare && activeA !== undefined && activeB !== undefined ? (
              <>
                <div className="season-year-fields">
                  <div className="detail-field">
                    <label htmlFor="season-year-a">{spanish ? "Año A" : "Year A"}</label>
                    <select id="season-year-a" value={activeA} onChange={(event) => setYears(Number(event.target.value), activeB)}>
                      {years.map((year) => <option value={year} key={year}>{year}</option>)}
                    </select>
                  </div>
                  <div className="detail-field">
                    <label htmlFor="season-year-b">{spanish ? "Año B" : "Year B"}</label>
                    <select id="season-year-b" value={activeB} onChange={(event) => setYears(activeA, Number(event.target.value))}>
                      {years.map((year) => <option value={year} key={year}>{year}</option>)}
                    </select>
                  </div>
                </div>
                <table className="detail-table">
                  <caption>{readingMetric(metric, lang)}</caption>
                  <thead>
                    <tr>
                      <th scope="col">{spanish ? "Rotación" : "Rotation"}</th>
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
            <p className="detail-footnote">{spanish ? "2026 queda en seguimiento. La comparación usa otros años de la muestra." : "Monitoring for 2026 is ongoing. The comparison uses other years from the sample."}</p>
          </section>
        </div>
      </article>
    </div>
  );
}
