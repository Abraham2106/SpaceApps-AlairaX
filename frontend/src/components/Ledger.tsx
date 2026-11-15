import { translate } from "../lib/i18n";
import { comparisonError } from "../lib/api";
import type { LoadedComparison } from "../lib/types";
import type { Lang } from "../lib/types";

export function Ledger({ loaded, lang }: { loaded: LoadedComparison; lang: Lang }) {
  const compare = loaded.compare;
  const versions = compare
    ? [...new Set(compare.rotations.flatMap((rotation) => rotation.runs.map((run) => run.model_version)))]
    : [];
  const assumptions = compare?.rotations[0]?.runs[0]?.assumptions ?? [];
  return (
    <section className="stack" aria-label={translate(lang, "common.calculationRecord")}>
      <p className="kicker">{translate(lang, "ledger.record")}</p>
      <p>
        {loaded.mode === "live"
          ? translate(lang, "ledger.thisDescribesApiResponse")
          : translate(lang, loaded.catalog.mock ? "ledger.thisDescribesFixtureNoBackend" : "ledger.staticResult")}
      </p>
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
            {translate(lang, "ledger.zone")}: {compare.zona.name} ({compare.zona.latitude}, {compare.zona.longitude}).{" "}
            {compare.zona.validated
              ? translate(lang, "ledger.markedValidated")
              : translate(lang, "ledger.itNotValidated")}
          </p>
          <p>
            {translate(lang, "ledger.modelVersionOnRuns")}: {versions.join(", ") || (translate(lang, "common.noData"))}.
          </p>
          <p>
            {translate(lang, "ledger.uncertaintyMethod")}: {compare.uncertainty_method}.
          </p>
          <ul>
            {compare.warnings.map((warning) => <li key={warning}>{warning}</li>)}
            {compare.limitations.map((warning) => <li key={warning}>{warning}</li>)}
            {assumptions.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
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
