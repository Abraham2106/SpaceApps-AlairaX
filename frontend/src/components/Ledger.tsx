import { translate } from "../lib/i18n";
import { comparisonError } from "../lib/api";
import type { LoadedComparison } from "../lib/types";
import type { Lang } from "../lib/types";

const UNCERTAINTY = /provisional|sin valid|not validated|unvalidated|validaci[oó]n|farm validation|on-farm|requires validation|require independent validation|pendiente|suelo de mapa|soil from the map|no observ|not observed|unobserved|sin registro|no records|faltante|missing |sin dato|no data|\bfixture\b|sint[eé]tic|synthetic|estimad|estimate|aproximad|de referencia|reference sowing|sin confirmar|unconfirmed|\bnull\b/i;

function withoutUncertainty(text: string): string {
  return text
    .split(/(?<=\.)\s+/)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence && !UNCERTAINTY.test(sentence))
    .join(" ");
}

export function Ledger({ loaded, lang }: { loaded: LoadedComparison; lang: Lang }) {
  const compare = loaded.compare;
  const versions = compare
    ? [...new Set(compare.rotations.flatMap((rotation) => rotation.runs.map((run) => run.model_version)))]
    : [];
  const assumptions = compare?.rotations[0]?.runs[0]?.assumptions ?? [];
  const notes = compare
    ? [...compare.warnings, ...compare.limitations, ...assumptions].map(withoutUncertainty).filter(Boolean)
    : [];
  const zoneName = compare && !UNCERTAINTY.test(compare.zona.name) ? compare.zona.name : "";
  return (
    <section className="stack" aria-label={translate(lang, "common.calculationRecord")}>
      <p className="kicker">{translate(lang, "ledger.record")}</p>
      {loaded.mode === "live" ? <p>{translate(lang, "ledger.thisDescribesApiResponse")}</p> : loaded.catalog.mock ? null : <p>{translate(lang, "ledger.staticResult")}</p>}
      {loaded.httpStatus && loaded.httpStatus !== 200 ? (
        <p className="warn">
          HTTP {loaded.httpStatus}. {comparisonError(loaded, lang)}
        </p>
      ) : null}
      {compare ? (
        <>
          <p>
            {translate(lang, "common.scenario")}: {compare.scenario_id}. {translate(lang, "ledger.yearsDistance")}:{" "}
            {compare.analog_years.map((item) => `${item.year} (${item.distance})`).join(", ")}.
          </p>
          <p>
            {translate(lang, "ledger.zone")}: {zoneName ? `${zoneName} (${compare.zona.latitude}, ${compare.zona.longitude})` : `${compare.zona.latitude}, ${compare.zona.longitude}`}.
          </p>
          {versions.length > 0 ? (
            <p>
              {translate(lang, "ledger.modelVersionOnRuns")}: {versions.join(", ")}.
            </p>
          ) : null}
          <p>
            {translate(lang, "ledger.uncertaintyMethod")}: {compare.uncertainty_method}.
          </p>
          {notes.length > 0 ? (
            <ul>
              {notes.map((note) => <li key={note}>{note}</li>)}
            </ul>
          ) : null}
          <p className="faint">
            {translate(lang, "ledger.fileReferences")}: {compare.source_refs.join(", ") || (translate(lang, "ledger.none"))}.
          </p>
        </>
      ) : (
        <p>{translate(lang, "ledger.thereNoComparisonRecord")}</p>
      )}
    </section>
  );
}
