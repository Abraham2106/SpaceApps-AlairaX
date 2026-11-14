import { ComparisonTable, DeltaChart, LevelChart } from "../components/Charts";
import { Ledger } from "../components/Ledger";
import { useComparison } from "../data/queries";
import { compactLine, metricNoun, rotationName, ROTATION_ORDER } from "../lib/plain";
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
        <h1>{spanish ? metricNoun(metric, lang) : metricNoun(metric, lang)}</h1>
        <p>
          {spanish
            ? "La escala del primer gráfico empieza en cero para no agrandar una diferencia chica. El segundo muestra solo el delta que ya trae el contrato, contra arroz → melón."
            : "The first chart starts at zero so a small difference is not enlarged. The second shows only the delta the contract already carries, against rice → melon."}
        </p>
        {comparison.isPending ? <p>{spanish ? "Cargando…" : "Loading…"}</p> : null}
        {comparison.isError ? <p className="warn">{(comparison.error as Error).message}</p> : null}
        {loaded && !compare ? <p className="warn">{loaded.httpDetail}</p> : null}
        {compare ? (
          <>
            <p>
              {spanish
                ? "p10–p90 es la variación entre los años análogos, no una probabilidad ni un intervalo de confianza. No es rendimiento, ni ahorro, ni una rotación ganadora."
                : "p10–p90 is the spread across the analog years, not a probability and not a confidence interval. This is not yield, not savings, and not a winning rotation."}
            </p>
            {ROTATION_ORDER.map((id) => {
              const rotation = compare.rotations.find((item) => item.rotation_id === id);
              if (!rotation) return null;
              const scenarioName = loaded?.catalog.scenarios.find((item) => item.id === compare.scenario_id)?.name ?? compare.scenario_id;
              return (
                <p key={id}>
                  {compactLine({
                    lang,
                    scenarioName,
                    metric,
                    rotationName: rotationName(id, lang, names[id]),
                    baselineName: rotationName(compare.baseline_rotation_id, lang, names[compare.baseline_rotation_id]),
                    isBaseline: id === compare.baseline_rotation_id,
                    p50: rotation.metrics[metric].p50,
                    deltaP50: rotation.delta_vs_baseline[metric].p50,
                    n: rotation.metrics[metric].n,
                    like2026: compare.scenario_id === "like_2026",
                  })}
                </p>
              );
            })}
            <LevelChart compare={compare} metric={metric} lang={lang} names={names} />
            <DeltaChart compare={compare} metric={metric} lang={lang} names={names} />
            <ComparisonTable compare={compare} metric={metric} lang={lang} names={names} />
            <Ledger loaded={loaded} lang={lang} />
          </>
        ) : null}
      </article>
    </div>
  );
}
