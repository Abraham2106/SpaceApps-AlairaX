import { translate } from "../lib/i18n";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowUpRight, LocateFixed, MapPin, Share2 } from "lucide-react";
import { TickScale } from "../components/Instrument";
import { formatNumber, formatValue, metricUnit } from "../lib/format";
import { cantonAt } from "../lib/geo";
import { surfaceCanton, surfaceDomain, useSurface } from "../lib/surface";
import { ROTATION_ORDER, comparisonSentence, leadSentence, readingMetric, rotationName } from "../lib/plain";
import { useCantons, useComparison } from "../data/queries";
import { comparisonError } from "../lib/api";
import { isCantonBoundaryMessage, useInstrument } from "../store";
import { QueryState } from "../components/QueryState";
import { Dialog } from "../components/Dialog";
import { RotationInsights } from "../components/RotationInsights";
import { Button, buttonVariants } from "../components/ui/button";
import { METRIC_IDS, SCENARIO_IDS, type MetricId, type ScenarioId } from "../lib/types";

export function MapReading() {
  const lang = useInstrument((state) => state.lang);
  const metric = useInstrument((state) => state.metric);
  const setMetric = useInstrument((state) => state.setMetric);
  const scenarioId = useInstrument((state) => state.scenarioId);
  const setScenario = useInstrument((state) => state.setScenario);
  const selectOnly = useInstrument((state) => state.selectOnly);
  const selected = useInstrument((state) => state.selected);
  const locationMessage = useInstrument((state) => state.locationMessage);
  const setLocation = useInstrument((state) => state.setLocation);
  const [params] = useSearchParams();
  const [ask, setAsk] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [copyStatus, setCopyStatus] = useState<"copied" | "failed" | null>(null);
  const cantons = useCantons();
  const surface = useSurface();
  const comparison = useComparison();
  const loaded = comparison.data;
  const compare = loaded?.compare ?? null;
  const names = Object.fromEntries((loaded?.catalog.rotations ?? []).map((item) => [item.id, item.name]));
  const scenarioName = compare ? translate(lang, `scenario.${compare.scenario_id}`) : "";

  const n = compare?.analog_years.length ?? 0;
  const modelCanton = compare && cantons.data ? cantonAt(compare.zona.longitude, compare.zona.latitude, cantons.data) : null;
  const selectedId = selected.length === 1 ? selected[0] : null;
  const cantonEntry = surfaceCanton(surface.data, selectedId ?? undefined);
  const loadingComparison = comparison.isPending;
  const readingCanton = Boolean(compare && cantonEntry && selectedId && selectedId !== modelCanton?.id);
  const cantonDemands = surface.data ? Object.values(surface.data.cantons).map((item) => item.water_demand_mm) : [];
  const cantonRank = cantonEntry ? [...cantonDemands].sort((a, b) => a - b).indexOf(cantonEntry.water_demand_mm) + 1 : 0;
  const [cantonMin, cantonMax] = surfaceDomain(surface.data);
  const baselineId = compare?.baseline_rotation_id ?? "rice_melon";
  const baselineName = rotationName(baselineId, lang, names[baselineId]);
  const amount = compare?.rotations.find(({ rotation_id }) => rotation_id === baselineId)?.metrics[metric].p50 ?? null;

  const shareText = compare
    ? [
        leadSentence(lang, scenarioName, metric, n),
        ...ROTATION_ORDER.map((id) => {
          const rotation = compare.rotations.find((item) => item.rotation_id === id);
          if (!rotation) return "";
          return comparisonSentence({
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
          });
        }),
        window.location.href,
      ].filter(Boolean).join("\n\n")
    : translate(lang, "mapReading.thereNoComparisonShareYet");

  function locate() {
    setAsk(false);
    const boundaries = cantons.data;
    if (!boundaries) return;
    if (!navigator.geolocation) {
      setLocation(null, { key: "mapReading.thisBrowserDoesNotProvide" });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const hit = cantonAt(position.coords.longitude, position.coords.latitude, boundaries);
        const inside = Boolean(hit?.properties.guanacaste);
        setLocation(
          {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            inside,
            cantonId: hit?.id ?? null,
            cantonName: hit?.properties.name ?? null,
          },
          inside
            ? { key: "mapReading.locationItOnlyRecentersMap", values: { canton: hit?.properties.name ?? "Guanacaste" } }
            : { key: "mapReading.thisPointOutsideGuanacasteModel" },
        );
      },
      () => setLocation(null, { key: "mapReading.locationWasDeniedYouCan" }),
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 },
    );
  }


  const es = lang === "es";
  const spread = compare?.rotations.flatMap(({ metrics }) => [metrics[metric].p10, metrics[metric].p90]).filter((value): value is number => value !== null) ?? [];
  const ranked = compare?.rotations.map(({ rotation_id, metrics }) => ({ id: rotation_id, value: metrics[metric].p50 }))
    .filter((item) => item.value !== null).sort((a, b) => (a.value ?? 0) - (b.value ?? 0)) ?? [];
  const rank = ranked.findIndex(({ id }) => id === baselineId) + 1;
  const rankText = rank === 0 ? "" : es
    ? `${rank}.º de ${ranked.length} rotaciones`
    : `${rank} of ${ranked.length} rotations`;
  return (
    <>
      <aside className="map-note" aria-label={es ? "Lectura del punto" : "Model location reading"}>
        <div className="note-head">
          <p className="map-note-site"><MapPin size={13} strokeWidth={1.8} aria-hidden /> {loadingComparison && cantonEntry ? cantonEntry.name : readingCanton && cantonEntry ? cantonEntry.name : `${modelCanton?.properties.name ?? "Guanacaste"} · ${translate(lang, `scenario.${scenarioId}`)}`}</p>
        </div>
        <h1>{readingCanton ? translate(lang, "mapReading.cantonDemand") : readingMetric(metric, lang)}</h1>
        <QueryState pending={false} error={comparison.isError} onRetry={() => comparison.refetch()} lang={lang} />
        {loadingComparison && <div className="map-reading-skeleton" role="status" aria-label={translate(lang, "queryState.loadingComparison")}>
          <span className="sr-only">{translate(lang, "queryState.loadingComparison")}</span>
          <div aria-hidden="true">
            <span className="skeleton-block skeleton-value" />
            <span className="skeleton-block skeleton-caption" />
            <div className="skeleton-scale"><span className="skeleton-block skeleton-label" /><span className="skeleton-block skeleton-bar" /><span className="skeleton-block skeleton-caption" /></div>
            <span className="skeleton-block skeleton-button" />
            <span className="skeleton-block skeleton-row" />
            <span className="skeleton-block skeleton-row" />
            <span className="skeleton-block skeleton-row" />
          </div>
        </div>}
        {loaded && !compare && !readingCanton && <p className="warn" role="alert">{comparisonError(loaded, lang)}</p>}
        {readingCanton && cantonEntry ? (
          <>
            <p className="readout">
              {formatNumber(cantonEntry.water_demand_mm, lang)}<small> mm</small>
            </p>
            <p className="note-ref">{translate(lang, "mapReading.cantonWindow")}</p>
            <div className="note-scale">
              <div className="scale-head">
                <span>{translate(lang, "mapReading.amongCantons")}</span>
                <strong>{translate(lang, "mapReading.cantonRank", { rank: cantonRank, total: cantonDemands.length })}</strong>
              </div>
              <TickScale value={cantonEntry.water_demand_mm} min={cantonMin} max={cantonMax} ticks={44}
                startLabel={`${formatNumber(cantonMin, lang, 0)} mm`} endLabel={`${formatNumber(cantonMax, lang, 0)} mm`}
                label={`${cantonEntry.name}: ${formatNumber(cantonEntry.water_demand_mm, lang)} mm`} />
            </div>
            <p className="note-ref">{translate(lang, "mapReading.cantonClimate", {
              rain: formatNumber(cantonEntry.rain_mm, lang),
              et0: formatNumber(cantonEntry.et0_mm, lang),
            })}</p>
          </>
        ) : null}
        {compare && !readingCanton && (
          <>
            {amount !== null ? (
              <p className="readout">
                {formatNumber(amount, lang)}<small> {metricUnit(metric, lang)}</small>
              </p>
            ) : null}
            <p className="note-ref">{baselineName} · {es ? "mediana de" : "median of"} {n} {es ? "temporadas" : "seasons"}</p>
            {spread.length > 0 ? (
              <div className="note-scale">
                <div className="scale-head">
                  <span>{es ? "Frente a las otras rotaciones" : "Against the other rotations"}</span>
                  <strong>{rankText}</strong>
                </div>
                <TickScale value={amount} min={Math.min(...spread)} max={Math.max(...spread)} ticks={44}
                  startLabel={formatValue(Math.min(...spread), metric, lang)} endLabel={formatValue(Math.max(...spread), metric, lang)}
                  label={`${baselineName}: ${formatValue(amount, metric, lang)}. ${rankText}`} />
              </div>
            ) : null}
            <Link className={`map-note-compare ${buttonVariants.default}`} to={{ pathname: "/", search: params.toString() }}>
              {es ? "Comparar rotaciones" : "Compare rotations"} <ArrowUpRight size={15} aria-hidden />
            </Link>
          </>
        )}
        {!loadingComparison && !readingCanton ? <div className="map-note-options map-reading-selects">
          <label>
            {lang === "es" ? "Clima" : "Climate"}
            <select value={scenarioId} onChange={(event) => setScenario(event.target.value as ScenarioId)}>
              {SCENARIO_IDS.map((id) => <option value={id} key={id}>{translate(lang, `scenario.${id}`)}</option>)}
            </select>
          </label>
          <label>
            {lang === "es" ? "Qué ver" : "What to show"}
            <select value={metric} onChange={(event) => setMetric(event.target.value as MetricId)}>
              {METRIC_IDS.map((id) => <option value={id} key={id}>{readingMetric(id, lang)}</option>)}
            </select>
          </label>
        </div> : null}
        {compare && !readingCanton ? <RotationInsights compare={compare} metric={metric} lang={lang} /> : null}
        <details className="map-note-more">
          <summary>{lang === "es" ? "Ubicación y compartir" : "Location and sharing"}</summary>
          <div className="map-note-options">
            <p>{translate(lang, "mapReading.cantonScope")}</p>
            <div className="map-note-actions">
              <button type="button" disabled={!cantons.data} onClick={() => setAsk(true)}><LocateFixed size={15} aria-hidden /> {translate(lang, "mapReading.useMyLocation")}</button>
              <button type="button" disabled={!modelCanton} onClick={() => {
                if (modelCanton && compare) selectOnly(modelCanton.id, [compare.zona.longitude, compare.zona.latitude]);
              }}>{translate(lang, "mapReading.goModelPoint")}</button>
              <button type="button" disabled={!compare} onClick={() => { setCopyStatus(null); setShareOpen(true); }}>
                <Share2 size={15} aria-hidden /> {translate(lang, "mapReading.share")}
              </button>
            </div>
          </div>
        </details>
        {cantons.isError && <p className="warn" role="alert">{translate(lang, "map.searchError")}</p>}
        {locationMessage && !isCantonBoundaryMessage(locationMessage) &&
          <p className="map-note-caption" role="status">{translate(lang, locationMessage.key, locationMessage.values)}</p>}
      </aside>
      {ask ? (
        <Dialog labelledBy="loc-title" onClose={() => setAsk(false)}>
          <h2 id="loc-title">{translate(lang, "mapReading.thisDeviceSLocation")}</h2>
          <p>{translate(lang, "mapReading.browserWillAskPermissionCoordinate")}</p>
          <div className="dialog-actions">
            <Button variant="outline" type="button" onClick={() => setAsk(false)}>{translate(lang, "mapReading.notNow")}</Button>
            <Button type="button" onClick={locate}>{translate(lang, "mapReading.askPermission")}</Button>
          </div>
        </Dialog>
      ) : null}
      {shareOpen ? (
        <Dialog labelledBy="share-title" onClose={() => setShareOpen(false)}>
          <h2 id="share-title">{translate(lang, "mapReading.shareThisReading")}</h2>
          <textarea readOnly value={shareText} aria-label={translate(lang, "mapReading.textShare")} />
          <div className="dialog-actions">
            <button type="button" className="btn btn-primary" onClick={async () => {
              try {
                await navigator.clipboard.writeText(shareText);
                setCopyStatus("copied");
              } catch {
                setCopyStatus("failed");
              }
            }}>{translate(lang, "mapReading.copy")}</button>
            <button type="button" className="btn btn-quiet" onClick={() => setShareOpen(false)}>{translate(lang, "common.close")}</button>
          </div>
          {copyStatus ? <p role="status">{translate(lang, copyStatus === "copied" ? "mapReading.copied" : "mapReading.copyFailed")}</p> : null}
        </Dialog>
      ) : null}
    </>
  );
}
