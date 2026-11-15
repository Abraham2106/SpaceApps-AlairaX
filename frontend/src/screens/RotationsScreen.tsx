import { ComparisonTable, DeltaChart, LevelChart } from "../components/Charts";
import { Ledger } from "../components/Ledger";
import { QueryState } from "../components/QueryState";
import { useComparison } from "../data/queries";
import { metricNoun } from "../lib/plain";
import { useInstrument } from "../store";

export function RotationsScreen() {
  const lang = useInstrument((state) => state.lang);
  const metric = useInstrument((state) => state.metric);
  const spanish = lang === "es";
  const comparison = useComparison();
  const loaded = comparison.data;
  const compare = loaded?.compare;
  const names = Object.fromEntries((loaded?.catalog.rotations ?? []).map((item) => [item.id, item.name]));

  return (
    <div className="screen">
      <article className="section stack">
        <p className="kicker">{spanish ? "Tres rotaciones, un mismo clima" : "Three rotations, one climate"}</p>
        <h1>{metricNoun(metric, lang)}</h1>
        <p>
          {spanish
            ? "p10–p90 es la variación entre los años análogos, no una probabilidad ni un intervalo de confianza. No es rendimiento, ni ahorro, ni una rotación ganadora."
            : "p10–p90 is the spread across the analog years, not a probability and not a confidence interval. This is not yield, not savings, and not a winning rotation."}
        </p>
        <QueryState pending={comparison.isPending} error={comparison.isError} onRetry={() => comparison.refetch()} lang={lang} />
        {loaded && !compare ? <p className="warn">{loaded.httpDetail}</p> : null}
        {compare && loaded ? (
          <>
            <DeltaChart compare={compare} metric={metric} lang={lang} names={names} />
            <ComparisonTable compare={compare} metric={metric} lang={lang} names={names} />
            <LevelChart compare={compare} metric={metric} lang={lang} names={names} />
            <details>
              <summary>{spanish ? "Registro del cálculo" : "Calculation record"}</summary>
              <Ledger loaded={loaded} lang={lang} />
            </details>
          </>
        ) : null}
      </article>
    </div>
  );
}
