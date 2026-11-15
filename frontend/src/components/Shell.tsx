import { translate } from "../lib/i18n";
import { NavLink, Outlet, useLocation, useSearchParams } from "react-router-dom";
import { useEffect, useRef } from "react";
import { Droplets, Grid2x2, Languages, Map, ShieldCheck, Sprout } from "lucide-react";
import { MapViewport } from "../map/MapViewport";
import { RadioGroup } from "./RadioGroup";
import { useComparison } from "../data/queries";
import { useInstrument } from "../store";
import { SCENARIO_IDS } from "../lib/types";
import { comparisonError } from "../lib/api";
import { AgricultureChat } from "./AgricultureChat";

const LINKS = [
  { to: "/", label: "common.rotations", icon: Sprout },
  { to: "/mapa", label: "common.map", icon: Map },
  { to: "/cantones", label: "common.cantons", icon: Grid2x2 },
  { to: "/temporada", label: "common.season", icon: Droplets },
  { to: "/confianza", label: "common.trust", icon: ShieldCheck },
] as const;

function BrandMark() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 20V4l16 16V4" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Shell() {
  const lang = useInstrument((state) => state.lang);
  const theme = useInstrument((state) => state.theme);
  const setLang = useInstrument((state) => state.setLang);
  const scenarioId = useInstrument((state) => state.scenarioId);
  const selected = useInstrument((state) => state.selected);
  const yearA = useInstrument((state) => state.yearA);
  const yearB = useInstrument((state) => state.yearB);
  const basemap = useInstrument((state) => state.basemap);
  const imageryDate = useInstrument((state) => state.imageryDate);
  const setScenario = useInstrument((state) => state.setScenario);
  const metric = useInstrument((state) => state.metric);
  const setMetric = useInstrument((state) => state.setMetric);
  const apiBase = useInstrument((state) => state.apiBase);
  const hydrate = useInstrument((state) => state.hydrate);
  const toParams = useInstrument((state) => state.toParams);
  const comparison = useComparison();
  const content = useRef<HTMLElement>(null);
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const isReplay = location.pathname === "/";
  const showMap = location.pathname === "/mapa";
  const scenarios = SCENARIO_IDS.map((value) => ({ value, label: translate(lang, `scenario.${value}`) }));

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.lang = lang;
  }, [theme, lang]);

  useEffect(() => {
    hydrate(params);
    // Hydrate once from the shared link. Later edits flow outward.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const next = toParams();
    if (next.toString() !== params.toString()) setParams(next, { replace: true });
  }, [scenarioId, metric, theme, lang, selected, yearA, yearB, basemap, imageryDate, params, setParams, toParams]);

  const liveFailure = comparison.data?.mode === "live" && comparison.data.httpStatus !== 200;

  return (
    <div className={showMap ? "app app-map" : "app"}>
      <div className="field-grain" aria-hidden="true" />
      <a className="skip" href="#contenido" onClick={(event) => {
        event.preventDefault();
        content.current?.focus();
      }}>{translate(lang, "shell.skipContent")}</a>
      <nav className="rail" aria-label={translate(lang, "shell.sections")}>
        <NavLink className="rail-brand" to={{ pathname: "/", search: params.toString() }} aria-label="NandaView" title="NandaView">
          <BrandMark />
        </NavLink>
        {LINKS.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={{ pathname: to, search: params.toString() }} title={translate(lang, label)} end
            aria-current={to === "/" && location.pathname === "/rotaciones" ? "page" : undefined}>
            <Icon size={18} strokeWidth={1.7} aria-hidden />
            <span className="rail-label">{translate(lang, label)}</span>
          </NavLink>
        ))}
        <span className="rail-spacer" />
        <button type="button" className="rail-lang" onClick={() => setLang(lang === "es" ? "en" : "es")} aria-label={translate(lang, "shell.switchLanguageLabel")}>
          <Languages size={16} strokeWidth={1.7} aria-hidden />
          <span>{lang === "es" ? "EN" : "ES"}</span>
        </button>
      </nav>
      <main ref={content} id="contenido" className="stage" tabIndex={-1}>
        {!showMap && (
          <header className={isReplay ? "topbar topbar-replay" : "topbar"}>
            <NavLink className="brand" to={{ pathname: "/", search: params.toString() }}>
              <BrandMark />
              <strong>NandaView</strong>
            </NavLink>
            {!isReplay && <>
              <label className="only-mobile">
                <span className="sr-only">{translate(lang, "common.scenario")}</span>
                <select className="scenario-select" value={scenarioId} onChange={(event) => setScenario(event.target.value as typeof scenarioId)} aria-label={translate(lang, "common.scenario")}>
                  {scenarios.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <RadioGroup
                className="segment hide-mobile"
                label={translate(lang, "common.scenario")}
                value={scenarioId}
                onChange={setScenario}
                options={scenarios}
              />
              <RadioGroup
                className="segment metric-tabs"
                label={translate(lang, "shell.metric")}
                value={metric}
                onChange={setMetric}
                options={[
                  { value: "modeled_water_deficit_mm", label: translate(lang, "metric.water") },
                  { value: "crop_water_demand_mm", label: translate(lang, "metric.demand") },
                  { value: "water_stress_days", label: translate(lang, "metric.stress") },
                ]}
              />
            </>}
            <span className="spacer" />
            {liveFailure ? (
              <p className="chip chip-live" role="status">
                <strong>HTTP {comparison.data?.httpStatus}</strong>
                <span>{comparisonError(comparison.data, lang)}</span>
              </p>
            ) : null}
            {apiBase ? <span className="mode-pill">API</span> : null}
          </header>
        )}
        <div className="stage-body">
          <MapViewport visible={showMap} lang={lang} />
          <Outlet />
        </div>
      </main>
      <AgricultureChat />
    </div>
  );
}
