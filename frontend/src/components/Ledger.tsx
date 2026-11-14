import type { LoadedComparison } from "../lib/types";
import type { Lang } from "../lib/types";

export function Ledger({ loaded, lang }: { loaded: LoadedComparison; lang: Lang }) {
  const compare = loaded.compare;
  const versions = compare
    ? [...new Set(compare.rotations.flatMap((rotation) => rotation.runs.map((run) => run.model_version)))]
    : [];
  const assumptions = compare?.rotations[0]?.runs[0]?.assumptions ?? [];
  return (
    <section className="stack" aria-label={lang === "es" ? "Registro del cálculo" : "Calculation record"}>
      <p className="kicker">{lang === "es" ? "Registro" : "Record"}</p>
      <p>
        {loaded.mode === "fixtures"
          ? lang === "es"
            ? "Esto describe un fixture. No hubo una corrida del backend detrás de estos números."
            : "This describes a fixture. No backend run produced these numbers."
          : lang === "es"
            ? "Esto describe la respuesta de la API."
            : "This describes the API response."}
      </p>
      {loaded.httpStatus && loaded.httpStatus !== 200 ? (
        <p className="warn">
          HTTP {loaded.httpStatus}. {loaded.httpDetail}
        </p>
      ) : null}
      {compare ? (
        <>
          <p>
            {lang === "es" ? "Escenario" : "Scenario"}: {compare.scenario_id}. {lang === "es" ? "Años y distancia" : "Years and distance"}:{" "}
            {compare.analog_years.map((item) => `${item.year} (${item.distance})`).join(", ")}.
          </p>
          <p>
            {lang === "es" ? "Zona" : "Zone"}: {compare.zona.name} ({compare.zona.latitude}, {compare.zona.longitude}).{" "}
            {compare.zona.validated
              ? lang === "es" ? "Marcada como validada." : "Marked validated."
              : lang === "es" ? "No está validada." : "It is not validated."}
          </p>
          <p>
            {lang === "es" ? "Versión del modelo en las corridas" : "Model version on the runs"}: {versions.join(", ") || (lang === "es" ? "sin dato" : "no data")}.
          </p>
          <p>
            {lang === "es" ? "Método de incertidumbre" : "Uncertainty method"}: {compare.uncertainty_method}.
          </p>
          <ul>
            {compare.warnings.map((warning) => <li key={warning}>{warning}</li>)}
            {compare.limitations.map((warning) => <li key={warning}>{warning}</li>)}
            {assumptions.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
          <p className="faint">
            {lang === "es" ? "Referencias del archivo" : "File references"}: {compare.source_refs.join(", ") || (lang === "es" ? "ninguna" : "none")}.
          </p>
        </>
      ) : (
        <p>{lang === "es" ? "No hay comparación que registrar." : "There is no comparison to record."}</p>
      )}
    </section>
  );
}
