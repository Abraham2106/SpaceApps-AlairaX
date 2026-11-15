import { translate, type MessageKey } from "../lib/i18n";
import { useState, type FormEvent } from "react";
import { Ledger } from "../components/Ledger";
import { QueryState } from "../components/QueryState";
import { useComparison } from "../data/queries";
import { comparisonError, probeHealth } from "../lib/api";
import { useInstrument } from "../store";

export function TrustScreen() {
  const lang = useInstrument((state) => state.lang);
  const apiBase = useInstrument((state) => state.apiBase);
  const setApiBase = useInstrument((state) => state.setApiBase);
  const [draft, setDraft] = useState(apiBase);
  const [connecting, setConnecting] = useState(false);
  const [note, setNote] = useState<{ key: MessageKey; error: boolean } | null>(null);
  const comparison = useComparison();
  const loaded = comparison.data;
  const compare = loaded?.compare;
  const zona = compare?.zona ?? loaded?.catalog.zona;
  const missing = translate(lang, "common.noData");
  const failure = comparisonError(loaded, lang);

  const sources = [
    {
      name: "NASA POWER",
      use: translate(lang, "trust.climateInputApiRuns"),
      detail: translate(lang, "trust.dailyRainTemperaturesHumidityWind"),
    },
    {
      name: "NOAA ONI / RONI",
      use: translate(lang, "trust.selectionSimilarYears"),
      detail: translate(lang, "trust.identifiesClimatePhaseUsedBuild"),
    },
    {
      name: translate(lang, "trust.soilSources"),
      use: translate(lang, "trust.soilRainfallCrossCheckMethod"),
      detail: translate(lang, "trust.fao56SuppliesWaterBalance"),
    },
    {
      name: "NASA GIBS",
      use: translate(lang, "trust.mapImagery"),
      detail: translate(lang, "trust.modisTerra12March2024"),
    },
    {
      name: "Esri / Maxar",
      use: translate(lang, "trust.referencePhotography"),
      detail: translate(lang, "trust.defaultSatellitePhotographyOnMap"),
    },
    {
      name: translate(lang, "trust.awsRelief"),
      use: translate(lang, "trust.terrainLighting"),
      detail: translate(lang, "trust.regionalTilesCiteGmted2010Etopo1"),
    },
  ];

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (connecting) return;
    const value = draft.trim();
    if (!value) {
      setApiBase("");
      setNote({ key: "trust.sampleDataActive", error: false });
      return;
    }
    if (!/^https?:\/\//.test(value)) {
      setNote({ key: "trust.addressMustStartWithHttp", error: true });
      return;
    }
    setConnecting(true);
    setNote(null);
    try {
      const ok = await probeHealth(value);
      if (ok) {
        setApiBase(value);
        setNote({ key: "trust.apiRespondedScenarioBeingRequested", error: false });
      } else {
        setNote({ key: "trust.thatAddressDidNotAnswer", error: true });
      }
    } finally {
      setConnecting(false);
    }
  }

  return (
    <div className="screen">
      <article className="detail-page">
        <header className="detail-header">
          <h1>{translate(lang, "trust.trustProvenance")}</h1>
          <p>{translate(lang, "trust.whatHasBeenValidatedWhat")}</p>
        </header>
        <div className="detail-layout trust-layout">
          <section className="detail-panel trust-overview" aria-labelledby="trust-validation">
            <h2 id="trust-validation">{translate(lang, "trust.validationStatus")}</h2>
            <QueryState pending={comparison.isPending} error={comparison.isError} onRetry={() => comparison.refetch()} lang={lang} />
            {failure ? <p className="warn" role="alert">{failure}</p> : null}
            <dl className="trust-facts">
              <div>
                <dt>{translate(lang, "cantons.modelPoint")}</dt>
                <dd>{zona ? (zona.validated ? (translate(lang, "trust.markedAsValidated")) : (translate(lang, "trust.provisional"))) : missing}</dd>
              </div>
              <div>
                <dt>{translate(lang, "common.sampleYears")}</dt>
                <dd>{compare?.analog_years.length ?? missing}</dd>
              </div>
              <div>
                <dt>{translate(lang, "trust.et0Documentation")}</dt>
                <dd>{translate(lang, "trust.et0MethodReviewed")}</dd>
              </div>
              <div>
                <dt>{translate(lang, "trust.hydraulicProfile")}</dt>
                <dd>{translate(lang, "trust.approvalPending")}</dd>
              </div>
            </dl>
            <p className="detail-footnote">{translate(lang, "trust.et0ProfileReviewStatusComes")}</p>
          </section>
          <section className="detail-panel trust-sources" aria-labelledby="trust-sources">
            <h2 id="trust-sources">{translate(lang, "trust.sourcesTheirRole")}</h2>
            <ul className="source-list">
              {sources.map(({ name, use, detail }) => (
                <li key={name}>
                  <h3>{name}</h3>
                  <div>
                    <p className="source-use">{use}</p>
                    <p>{detail}</p>
                  </div>
                </li>
              ))}
            </ul>
            <details className="detail-disclosure">
              <summary>{translate(lang, "trust.nasaDataOutsideBalance")}</summary>
              <ul>
                <li><strong>GPM IMERG.</strong> {translate(lang, "trust.teamPlanLeftItOut")}</li>
                <li><strong>SMAP.</strong> {translate(lang, "trust.measuresSoilMoistureCoarseResolution")}</li>
                <li><strong>HLS.</strong> {translate(lang, "trust.30MResolutionCouldHelp")}</li>
              </ul>
            </details>
          </section>
          <details className="detail-panel detail-disclosure trust-api">
            <summary>{translate(lang, "trust.connectApi")}</summary>
            <div>
            <p id="api-help" className="detail-lead">
              {translate(lang, "trust.leaveAddressEmptyUseSample")}
            </p>
            <form className="trust-form" onSubmit={connect}>
              <label className="detail-field">{translate(lang, "trust.apiAddress")}
                <input className="search" type="text" inputMode="url" spellCheck={false} autoComplete="off" aria-describedby="api-help" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="http://127.0.0.1:8000" disabled={connecting} />
              </label>
              <button type="submit" disabled={connecting}>{connecting ? (translate(lang, "trust.checking")) : (translate(lang, "trust.connect"))}</button>
            </form>
            {connecting ? <p className="detail-footnote" role="status">{translate(lang, "trust.checkingHealth")}</p> : null}
            {note ? <p className={note.error ? "warn" : "detail-footnote"} role={note.error ? "alert" : "status"}>{translate(lang, note.key)}</p> : null}
            </div>
          </details>
          {loaded ? (
            <details className="detail-panel detail-disclosure trust-record">
              <summary>{translate(lang, "common.calculationRecord")}</summary>
              <Ledger loaded={loaded} lang={lang} />
            </details>
          ) : null}
        </div>
      </article>
    </div>
  );
}
