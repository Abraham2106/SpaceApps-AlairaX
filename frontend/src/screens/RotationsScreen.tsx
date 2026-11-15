import { useState } from "react";
import { ComparisonResults, ComparisonSkeleton, ComparisonViewPicker, type ComparisonView } from "../components/Charts";
import { Ledger } from "../components/Ledger";
import { QueryState } from "../components/QueryState";
import { useComparison } from "../data/queries";
import { readingMetric, readingNotes } from "../lib/plain";
import { useInstrument } from "../store";

export function RotationsScreen() {
  const lang = useInstrument((state) => state.lang);
  const metric = useInstrument((state) => state.metric);
  const spanish = lang === "es";
  const [view, setView] = useState<ComparisonView>("chart");
  const comparison = useComparison();
  const loaded = comparison.data;
  const compare = loaded?.compare;
  const names = Object.fromEntries((loaded?.catalog.rotations ?? []).map((item) => [item.id, item.name]));

  return (
    <div className="screen">
      <article className="rotations-section">
        <header className="comparison-header">
          <h1>{readingMetric(metric, lang)}</h1>
          <ComparisonViewPicker view={view} onChange={setView} lang={lang} />
        </header>
        {view === "chart" ? (
          <p className="comparison-key">
            {spanish ? "Banda de p10 a p90 · Raya en la mediana (p50)" : "Band from p10 to p90 · Tick at the median (p50)"}
          </p>
        ) : null}
        <QueryState pending={comparison.isPending} error={comparison.isError} onRetry={() => comparison.refetch()} lang={lang} />
        {loaded && !compare ? <p className="warn" role="alert">{loaded.httpDetail}</p> : null}
        <div aria-busy={comparison.isPending}>
          {comparison.isPending ? <ComparisonSkeleton view={view} /> : null}
          {compare ? <ComparisonResults compare={compare} metric={metric} lang={lang} names={names} view={view} /> : null}
        </div>
        {compare && loaded ? (
          <>
            <p className="comparison-note">{readingNotes(lang, compare.scenario_id === "like_2026")}</p>
            <details className="comparison-ledger">
              <summary>{spanish ? "Registro del cálculo" : "Calculation record"}</summary>
              <Ledger loaded={loaded} lang={lang} />
            </details>
          </>
        ) : null}
      </article>
    </div>
  );
}
