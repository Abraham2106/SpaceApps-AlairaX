import { translate } from "../lib/i18n";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { LocateFixed, Share2 } from "lucide-react";
import { formatNumber, formatValue, metricUnit } from "../lib/format";
import { cantonAt } from "../lib/geo";
import { ROTATION_ORDER, comparisonSentence, leadSentence, readingMetric, readingNotes, rotationName } from "../lib/plain";
import { useCantons, useComparison } from "../data/queries";
import { comparisonError } from "../lib/api";
import { isCantonBoundaryMessage, useInstrument } from "../store";
import { QueryState } from "../components/QueryState";
import { Dialog } from "../components/Dialog";
import type { RotationId } from "../lib/types";
import { ReadingSheet } from "./ReadingSheet";
import { MapCantonList } from "./MapCantonList";

export function MapReading() {
  const lang = useInstrument((state) => state.lang);
  const metric = useInstrument((state) => state.metric);
  const selectOnly = useInstrument((state) => state.selectOnly);
  const location = useInstrument((state) => state.location);
  const locationMessage = useInstrument((state) => state.locationMessage);
  const setLocation = useInstrument((state) => state.setLocation);
  const [params] = useSearchParams();
  const [ask, setAsk] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [copyStatus, setCopyStatus] = useState<"copied" | "failed" | null>(null);
  const cantons = useCantons();
  const comparison = useComparison();
  const loaded = comparison.data;
  const compare = loaded?.compare ?? null;
  const names = Object.fromEntries((loaded?.catalog.rotations ?? []).map((item) => [item.id, item.name]));
  const scenarioName = compare ? translate(lang, `scenario.${compare.scenario_id}`) : "";

  const n = compare?.analog_years.length ?? 0;
  const modelCanton = compare && cantons.data ? cantonAt(compare.zona.longitude, compare.zona.latitude, cantons.data) : null;
  const baselineId = compare?.baseline_rotation_id ?? "rice_melon";
  const baselineName = rotationName(baselineId, lang, names[baselineId]);
  const version = compare?.rotations[0]?.runs[0]?.model_version ?? "";

  function reading(id: RotationId): { value: number | null; delta: number | null } {
    const rotation = compare?.rotations.find((item) => item.rotation_id === id);
    return {
      value: rotation?.metrics[metric].p50 ?? null,
      delta: id === compare?.baseline_rotation_id ? null : rotation?.delta_vs_baseline[metric].p50 ?? null,
    };
  }

  const lead = reading(baselineId);
  const barMax = Math.max(
    1,
    ...ROTATION_ORDER.map((id) => reading(id).value ?? 0),
  );

  const shareText = compare
    ? [
        leadSentence(lang, scenarioName, metric, n, compare._mock),
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


  return (
    <>
      <ReadingSheet title={readingMetric(metric, lang)} lang={lang}>
          <QueryState pending={comparison.isPending} error={comparison.isError} onRetry={() => comparison.refetch()} lang={lang} />
          {loaded && !compare ? <p className="warn" role="alert">{comparisonError(loaded, lang)}</p> : null}
          {compare ? (
            <div className="reading-lead">
              <p className={lead.value == null ? "reading-empty" : "readout"}>
                {lead.value == null ? formatValue(null, metric, lang) : (
                  <>{formatNumber(lead.value, lang)}<small> {metricUnit(metric, lang)}</small></>
                )}
                  {compare._mock ? <span className="reading-sample">{translate(lang, "shell.syntheticData")}</span> : null}
              </p>
              <p>{translate(lang, "mapReading.modelPoint", { baselineName })}</p>
            </div>
          ) : null}
          {compare ? (
            <details className="reading-details">
              <summary>{translate(lang, "mapReading.readMore")}</summary>
              <h2>{translate(lang, "mapReading.rotationComparison")}</h2>
              <div className="bullets">
                {ROTATION_ORDER.map((id) => {
                  const item = reading(id);
                  const width = item.value == null ? 0 : Math.min(100, (item.value / barMax) * 100);
                  return (
                    <div key={id} className="bullet" data-rot={id}>
                      <div className="bullet-top">
                        <span><i className="rot-bg" />{rotationName(id, lang, names[id])}</span>
                        <strong>{item.value == null ? (translate(lang, "common.noData")) : formatValue(item.value, metric, lang)}</strong>
                      </div>
                      <div className="bullet-track" aria-hidden>
                        {item.value == null ? null : <span className="bullet-bar" style={{ width: `${width}%` }} />}
                        {id !== baselineId && lead.value != null ? <span className="bullet-mark" style={{ left: `${(lead.value / barMax) * 100}%` }} /> : null}
                      </div>
                      <span className="bullet-delta">
                        {item.delta == null
                          ? id === baselineId ? (translate(lang, "mapReading.reference")) : (translate(lang, "mapReading.differenceNoData"))
                          : item.delta === 0
                            ? `${translate(lang, "mapReading.sameAs")} ${baselineName}`
                            : item.delta < 0
                              ? `${formatValue(Math.abs(item.delta), metric, lang)} ${translate(lang, "mapReading.lessThan")} ${baselineName}`
                              : `${formatValue(item.delta, metric, lang)} ${translate(lang, "mapReading.moreThan")} ${baselineName}`}
                      </span>
                    </div>
                  );
                })}
              </div>
              <h2>{translate(lang, "mapReading.howReadComparison")}</h2>
              <p>{leadSentence(lang, scenarioName, metric, n, compare._mock)}</p>
              <p>{readingNotes(lang, compare.scenario_id === "like_2026")}</p>
              {compare.warnings.length > 0 ? (
                <>
                  <h2>{translate(lang, "mapReading.warnings")}</h2>
                  <ul>{compare.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
                </>
              ) : null}
              {compare.limitations.length > 0 ? (
                <>
                  <h2>{translate(lang, "mapReading.limitations")}</h2>
                  <ul>{compare.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>
                </>
              ) : null}
              <p className="faint">
                {modelCanton ? translate(lang, "mapReading.pointInCanton", { canton: modelCanton.properties.name }) + " " : ""}
                {translate(lang, "mapReading.cantonScope")}
              </p>
              {version ? <p className="faint">{translate(lang, "mapReading.modelVersion")} <code>{version}</code></p> : null}
            </details>
          ) : null}
          <div className="row">
            <button type="button" disabled={!cantons.data} onClick={() => setAsk(true)}><LocateFixed size={16} strokeWidth={1.5} aria-hidden /> {translate(lang, "mapReading.useMyLocation")}</button>
            <button type="button" disabled={!modelCanton} onClick={() => {
              if (modelCanton && compare) selectOnly(modelCanton.id, [compare.zona.longitude, compare.zona.latitude]);
            }}>{translate(lang, "mapReading.goModelPoint")}</button>
          </div>
          {cantons.isError ? <p className="warn" role="alert">{translate(lang, "map.searchError")}</p> : null}
          {locationMessage && !isCantonBoundaryMessage(locationMessage)
            ? <p className="kicker" role="status">{translate(lang, locationMessage.key, locationMessage.values)}</p>
            : null}
          {location && !location.inside ? <p className="warn">{translate(lang, "mapReading.noExtrapolation")}</p> : null}
          <MapCantonList />
          <div className="row">
            <Link to={{ pathname: "/rotaciones", search: params.toString() }}>{translate(lang, "mapReading.seeChart")}</Link>
            <button type="button" onClick={() => { setCopyStatus(null); setShareOpen(true); }}><Share2 size={16} strokeWidth={1.5} aria-hidden /> {translate(lang, "mapReading.share")}</button>
          </div>
      </ReadingSheet>
      {ask ? (
        <Dialog labelledBy="loc-title" onClose={() => setAsk(false)}>
          <h2 id="loc-title">{translate(lang, "mapReading.thisDeviceSLocation")}</h2>
          <p>{translate(lang, "mapReading.browserWillAskPermissionCoordinate")}</p>
          <div className="row">
            <button type="button" onClick={locate}>{translate(lang, "mapReading.askPermission")}</button>
            <button type="button" onClick={() => setAsk(false)}>{translate(lang, "mapReading.notNow")}</button>
          </div>
        </Dialog>
      ) : null}
      {shareOpen ? (
        <Dialog labelledBy="share-title" onClose={() => setShareOpen(false)}>
          <h2 id="share-title">{translate(lang, "mapReading.shareThisReading")}</h2>
          <textarea readOnly value={shareText} aria-label={translate(lang, "mapReading.textShare")} />
          <div className="row">
            <button type="button" onClick={async () => {
              try {
                await navigator.clipboard.writeText(shareText);
                setCopyStatus("copied");
              } catch {
                setCopyStatus("failed");
              }
            }}>{translate(lang, "mapReading.copy")}</button>
            <button type="button" onClick={() => setShareOpen(false)}>{translate(lang, "common.close")}</button>
          </div>
          {copyStatus ? <p role="status">{translate(lang, copyStatus === "copied" ? "mapReading.copied" : "mapReading.copyFailed")}</p> : null}
        </Dialog>
      ) : null}
    </>
  );
}
