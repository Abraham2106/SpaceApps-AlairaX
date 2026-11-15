import { ArrowRight, ArrowUpRight, MapPin } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { QueryState } from "../components/QueryState";
import { ProfileCard, RankCard, SoilStorageCard, WeeklyHeatmap } from "../components/RotationInsights";
import { Figure, METRIC_ICON, StatGrid, StatusPill, TickScale, type Stat } from "../components/Instrument";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { buttonVariants } from "../components/ui/button";
import { useComparison } from "../data/queries";
import { comparisonError } from "../lib/api";
import { formatValue } from "../lib/format";
import { translate } from "../lib/i18n";
import { metricNoun, readingMetric, rotationName } from "../lib/plain";
import { METRIC_IDS, SCENARIO_IDS, type MetricId, type ScenarioId } from "../lib/types";
import { useInstrument } from "../store";

export function ReplayScreen() {
  const scenarioId = useInstrument((state) => state.scenarioId);
  const metric = useInstrument((state) => state.metric);
  const setScenario = useInstrument((state) => state.setScenario);
  const setMetric = useInstrument((state) => state.setMetric);
  const lang = useInstrument((state) => state.lang);
  const es = lang === "es";
  const [params] = useSearchParams();
  const comparison = useComparison();
  const loaded = comparison.data;
  const result = loaded?.compare;
  const baseline = result?.rotations.find(({ rotation_id }) => rotation_id === result.baseline_rotation_id);
  const years = result?.analog_years.map(({ year }) => year).sort((a, b) => a - b).join(" · ");

  const stats: Stat[] = baseline ? [
    ...METRIC_IDS.map((id) => ({
      id,
      label: readingMetric(id, lang),
      icon: METRIC_ICON[id],
      value: <Figure value={baseline.metrics[id].p50} metric={id} lang={lang} />,
      high: formatValue(baseline.metrics[id].p90, id, lang),
      low: formatValue(baseline.metrics[id].p10, id, lang),
      active: id === metric,
    })),
    {
      id: "seasons",
      label: es ? "Temporadas comparadas" : "Seasons compared",
      icon: METRIC_ICON.seasons,
      value: <span className="figure">{result?.analog_years.length ?? "—"}</span>,
      note: years,
    },
  ] : [];

  const spread = result?.rotations.flatMap(({ metrics }) => [metrics[metric].p10, metrics[metric].p90]).filter((value): value is number => value !== null) ?? [];
  const ranked = result?.rotations.map(({ rotation_id, metrics }) => ({ id: rotation_id, value: metrics[metric].p50 }))
    .filter((item): item is { id: typeof item.id; value: number } => item.value !== null)
    .sort((a, b) => a.value - b.value) ?? [];
  const rank = baseline ? ranked.findIndex(({ id }) => id === baseline.rotation_id) + 1 : 0;
  const rankText = rank === 0 ? "" : es
    ? `${rank}.º de ${ranked.length} · ${rank === 1 ? "el valor más bajo" : rank === ranked.length ? "el valor más alto" : "valor intermedio"}`
    : `${rank} of ${ranked.length} · ${rank === 1 ? "lowest value" : rank === ranked.length ? "highest value" : "middle value"}`;

  return (
    <div className="screen dash-screen">
      <div className="dash">
        <header className="dash-head">
          <div className="dash-title">
            <h1>{es ? "¿Qué sembrar después del arroz?" : "What could you plant after rice?"}</h1>
            <p><MapPin size={14} strokeWidth={1.8} aria-hidden /> Guanacaste, Costa Rica <span aria-hidden>·</span> {es ? "Melón, leguminosa y sorgo bajo el mismo clima histórico." : "Melon, legumes and sorghum under the same historical weather."}</p>
          </div>
          <div className="dash-actions">
            <label className="pill-field">
              <span>{es ? "Clima" : "Climate"}</span>
              <select aria-label={es ? "Clima" : "Climate"} value={scenarioId} onChange={(event) => setScenario(event.target.value as ScenarioId)}>
                {SCENARIO_IDS.map((id) => <option key={id} value={id}>{translate(lang, `scenario.${id}`)}</option>)}
              </select>
            </label>
            <label className="pill-field">
              <span>{es ? "Qué comparar" : "What to compare"}</span>
              <select aria-label={es ? "Qué comparar" : "What to compare"} value={metric} onChange={(event) => setMetric(event.target.value as MetricId)}>
                {METRIC_IDS.map((id) => <option key={id} value={id}>{readingMetric(id, lang)}</option>)}
              </select>
            </label>
            <Link className={buttonVariants.default} to={{ pathname: "/mapa", search: params.toString() }}>
              {es ? "Abrir mapa" : "Open map"} <ArrowUpRight size={15} aria-hidden />
            </Link>
          </div>
        </header>

        <div className="dash-grid">
          <Card className="overview-card">
            <CardHeader>
              <div className="overview-title">
                <h2>{baseline ? rotationName(baseline.rotation_id, lang) : (es ? "Rotación de referencia" : "Reference rotation")}</h2>
                {baseline ? <span className="ref-tag">{es ? "Referencia" : "Reference"}</span> : null}
              </div>
              {result?._mock ? <StatusPill>{translate(lang, "shell.syntheticData")}</StatusPill> : null}
              {result && !result._mock && !result.zona.validated ? <StatusPill>{translate(lang, "shell.regionalPilot")}</StatusPill> : null}
            </CardHeader>
            <CardContent>
              <QueryState pending={comparison.isPending} error={comparison.isError} onRetry={() => comparison.refetch()} lang={lang} />
              {loaded && !result && <p className="warn" role="alert">{comparisonError(loaded, lang)}</p>}
              {baseline ? <StatGrid stats={stats} lang={lang} /> : null}
              {baseline && spread.length > 0 ? (
                <section className="scale-strip" aria-labelledby="scale-title">
                  <div className="scale-head">
                    <h3 id="scale-title">{es ? "Posición entre las tres rotaciones" : "Position among the three rotations"}</h3>
                    <span>{rankText}</span>
                  </div>
                  <TickScale
                    value={baseline.metrics[metric].p50}
                    min={Math.min(...spread)}
                    max={Math.max(...spread)}
                    startLabel={formatValue(Math.min(...spread), metric, lang)}
                    endLabel={formatValue(Math.max(...spread), metric, lang)}
                    label={`${rotationName(baseline.rotation_id, lang)}: ${formatValue(baseline.metrics[metric].p50, metric, lang)}. ${rankText}`}
                  />
                  <p className="scale-foot">
                    {es
                      ? `Escala de ${metricNoun(metric, lang)}: del año más bajo al más alto de las tres rotaciones. Más a la izquierda es mejor.`
                      : `Scale of ${metricNoun(metric, lang)}: from the lowest to the highest year across all three rotations. Further left is better.`}
                  </p>
                </section>
              ) : null}
            </CardContent>
          </Card>
          {result ? (
            <>
              <div className="dash-side">
                <RankCard compare={result} metric={metric} lang={lang} />
                <ProfileCard compare={result} lang={lang} />
              </div>
              <SoilStorageCard compare={result} lang={lang} />
              <WeeklyHeatmap compare={result} lang={lang} />
            </>
          ) : null}
        </div>
        {result && (
          <footer className="dash-foot">
            <p>{es ? "Estimaciones del modelo. Requieren validación en finca." : "Model estimates. On-farm validation is needed."}</p>
            <Link className={buttonVariants.outline} to={{ pathname: "/rotaciones", search: params.toString() }}>
              {es ? "Ver cálculo y rangos" : "View calculations and ranges"} <ArrowRight size={15} aria-hidden />
            </Link>
          </footer>
        )}
      </div>
    </div>
  );
}
