import { useInstrument } from "../store";
import { useComparison } from "../data/queries";
import { formatValue } from "../lib/format";
import { ROTATION_ORDER, ROTATION_STYLE, rotationName } from "../lib/plain";
import { QueryState } from "../components/QueryState";

const MONTHS = [
  ["Abr", "Apr"],
  ["May", "May"],
  ["Jun", "Jun"],
  ["Jul", "Jul"],
  ["Ago", "Aug"],
  ["Sep", "Sep"],
  ["Oct", "Oct"],
  ["Nov", "Nov"],
  ["Dic", "Dec"],
];

export function SeasonScreen() {
  const lang = useInstrument((state) => state.lang);
  const spanish = lang === "es";
  const metric = useInstrument((state) => state.metric);
  const yearA = useInstrument((state) => state.yearA);
  const yearB = useInstrument((state) => state.yearB);
  const setYears = useInstrument((state) => state.setYears);
  const comparison = useComparison();
  const compare = comparison.data?.compare;
  const names = Object.fromEntries((comparison.data?.catalog.rotations ?? []).map((item) => [item.id, item.name]));
  const years = compare?.analog_years.map((item) => item.year) ?? [];
  const activeA = yearA ?? years[0] ?? null;
  const activeB = yearB ?? years[years.length - 1] ?? null;
  const daily = compare?.rotations.some((rotation) => rotation.runs.some((run) => run.daily_balance.length > 0)) ?? false;

  return (
    <div className="screen">
      <article className="section stack">
        <p className="kicker">{spanish ? "Abril a diciembre" : "April to December"}</p>
        <h1>{spanish ? "La temporada, con fechas sin validar" : "The season, with unvalidated dates"}</h1>
        <p>
          {spanish
            ? "La ventana de análogos documentada va del 1 de abril al 31 de octubre. El archivo de rotaciones, marcado verified: false, pone la siembra de arroz el 15 de mayo, caupí y sorgo el 15 de octubre, y melón el 1 de diciembre. No son observaciones de una finca."
            : "The documented analog window runs from 1 April to 31 October. The rotation file, marked verified: false, puts rice sowing on 15 May, cowpea and sorghum on 15 October, and melon on 1 December. These are not observations from a farm."}
        </p>
        <div className="timeline">
          {MONTHS.map(([es, en], index) => (
            <div key={es} className="month">
              <strong>{spanish ? es : en}</strong>
              {/* Las marcas repiten la lista de abajo; la lista es el texto que cuenta. */}
              {index === 0 ? <span className="mark" aria-hidden="true" style={{ background: "var(--mark-window)" }} /> : null}
              {index === 1 ? <span className="mark" aria-hidden="true" style={{ background: "var(--ink)" }} /> : null}
              {index === 6 ? (
                <span className="mark mark-split" aria-hidden="true">
                  <i style={{ background: ROTATION_STYLE.rice_legume.color }} />
                  <i style={{ background: ROTATION_STYLE.rice_sorghum.color }} />
                </span>
              ) : null}
              {index === 8 ? <span className="mark" aria-hidden="true" style={{ background: ROTATION_STYLE.rice_melon.color }} /> : null}
            </div>
          ))}
        </div>
        <ul>
          <li>{spanish ? "Abril: inicio de la ventana de comparación. No es una siembra." : "April: start of the comparison window. Not a sowing date."}</li>
          <li>{spanish ? "15 de mayo: siembra de referencia del arroz. Etapas FAO-56 Tabla 11, 30/30/60/30 días, verified false. El arroz del archivo es secano, no inundado." : "15 May: reference rice sowing. FAO-56 Table 11 stages, 30/30/60/30 days, verified false. The file’s rice is upland, not flooded."}</li>
          <li>{spanish ? "15 de octubre: siembra de referencia de caupí o de sorgo. El archivo de cultivos usa parámetros de sorgo grano aunque la rotación dice sorgo forrajero." : "15 October: reference sowing of cowpea or sorghum. The crop file uses grain-sorghum parameters even though the rotation says forage sorghum."}</li>
          <li>{spanish ? "31 de octubre: fin de la ventana de análogos." : "31 October: end of the analog window."}</li>
          <li>{spanish ? "1 de diciembre: siembra de referencia del melón, el único tramo con riego en el archivo. El ciclo sigue al año siguiente y no cabe entero en este eje." : "1 December: reference melon sowing, the only irrigated segment in the file. The cycle continues into the next year and does not fit entirely on this axis."}</li>
        </ul>
        <QueryState pending={comparison.isPending} error={comparison.isError} onRetry={() => comparison.refetch()} lang={lang} />
        {comparison.data && !daily ? (
          <p className="status-block">
            {spanish
              ? "Este resultado no trae balance diario. No se dibuja una curva inventada."
              : "This result has no daily balance. No invented curve is drawn."}
          </p>
        ) : null}
        {years.length > 1 && activeA && activeB ? (
          <>
            <div className="row">
              <label>{spanish ? "Año A" : "Year A"}
                <select value={activeA} onChange={(event) => setYears(Number(event.target.value), activeB)}>
                  {years.map((year) => <option key={year}>{year}</option>)}
                </select>
              </label>
              <label>{spanish ? "Año B" : "Year B"}
                <select value={activeB} onChange={(event) => setYears(activeA, Number(event.target.value))}>
                  {years.map((year) => <option key={year}>{year}</option>)}
                </select>
              </label>
            </div>
            <div className="year-grid">
              {[activeA, activeB].map((year) => (
                <section key={year}>
                  <h2 className="num">{year}</h2>
                  <table>
                    <caption>{year}</caption>
                    <tbody>
                      {ROTATION_ORDER.map((id) => {
                        const run = compare?.rotations.find((item) => item.rotation_id === id)?.runs.find((item) => item.year === year);
                        return (
                          <tr key={id}>
                            <th scope="row">{rotationName(id, lang, names[id])}</th>
                            <td>{formatValue(run?.metrics[metric] ?? null, metric, lang)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </section>
              ))}
            </div>
            <p className="faint">{spanish ? "Dos años del archivo, uno al lado del otro. 2026 no está entre ellos." : "Two years from the file, side by side. 2026 is not among them."}</p>
          </>
        ) : null}
      </article>
    </div>
  );
}
