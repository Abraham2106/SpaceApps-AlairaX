import { translate } from "../lib/i18n";
import { NavLink, Outlet, useLocation, useSearchParams } from "react-router-dom";
import { useEffect, useRef } from "react";
import { Droplets, Grid2x2, Leaf, Map, Moon, ShieldCheck, Sprout, SunMedium } from "lucide-react";
import { MapViewport } from "../map/MapViewport";
import { RadioGroup } from "./RadioGroup";
import { useComparison } from "../data/queries";
import { useInstrument } from "../store";
import { SCENARIO_IDS } from "../lib/types";
import { comparisonError } from "../lib/api";

const LINKS = [
  { to: "/", label: "common.map", icon: Map },
  { to: "/cantones", label: "common.cantons", icon: Grid2x2 },
  { to: "/rotaciones", label: "common.rotations", icon: Sprout },
  { to: "/temporada", label: "common.season", icon: Droplets },
  { to: "/confianza", label: "common.trust", icon: ShieldCheck },
] as const;

export function Shell() {
  const lang = useInstrument((state) => state.lang);
  const theme = useInstrument((state) => state.theme);
  const setLang = useInstrument((state) => state.setLang);
  const setTheme = useInstrument((state) => state.setTheme);
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
  const showMap = location.pathname === "/";
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

  const mock = comparison.data?.compare?._mock ?? comparison.data?.catalog.mock ?? true;
  const liveFailure = comparison.data?.mode === "live" && comparison.data.httpStatus !== 200;

  return (
    <div className="app">
      <a className="skip" href="#contenido" onClick={(event) => {
        event.preventDefault();
        content.current?.focus();
      }}>{translate(lang, "shell.skipContent")}</a>
      <header className="topbar">
        <NavLink className="brand" to={{ pathname: "/", search: params.toString() }}>
          <Leaf size={22} strokeWidth={1.5} aria-hidden />
          <span className="brand-name">
            <strong>NandaView</strong>
            <span>AlairaX</span>
          </span>
        </NavLink>
        <label className="only-mobile">
          <span className="kicker">{translate(lang, "common.scenario")}</span>
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
          className="metric-tabs"
          label={translate(lang, "shell.metric")}
          value={metric}
          onChange={setMetric}
          options={[
            { value: "modeled_water_deficit_mm", label: translate(lang, "metric.water") },
            { value: "crop_water_demand_mm", label: translate(lang, "metric.demand") },
            { value: "water_stress_days", label: translate(lang, "metric.stress") },
          ]}
        />
        <span className="spacer" />
        {mock && !liveFailure ? (
          <p className="chip" role="status">
            <strong>{translate(lang, "shell.sample")}</strong>
            <span className="chip-note">{translate(lang, "shell.syntheticData")}</span>
          </p>
        ) : null}
        {liveFailure ? (
          <p className="chip chip-live" role="status">
            <strong>HTTP {comparison.data?.httpStatus}</strong>
            <span>{comparisonError(comparison.data, lang)}</span>
          </p>
        ) : null}
        <span className="mode-pill">{apiBase ? "API" : translate(lang, "shell.fixture")}</span>
        <button onClick={() => setTheme(theme === "night" ? "sun" : "night")} aria-pressed={theme === "sun"}>
          {theme === "night" ? <Moon size={16} aria-hidden /> : <SunMedium size={16} aria-hidden />}
          <span className="btn-label">{theme === "night" ? (translate(lang, "shell.night")) : (translate(lang, "shell.sun"))}</span>
        </button>
        <button onClick={() => setLang(lang === "es" ? "en" : "es")} aria-label={translate(lang, "shell.switchLanguageLabel")}>
          {translate(lang, "shell.switchLanguage")}
        </button>
      </header>
      <div className="workspace">
        <nav className="rail" aria-label={translate(lang, "shell.sections")}>
          {LINKS.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink key={link.to} to={{ pathname: link.to, search: params.toString() }} end={link.to === "/"}>
                <Icon size={18} strokeWidth={1.5} aria-hidden />
                <span className="rail-label">{translate(lang, link.label)}</span>
              </NavLink>
            );
          })}
        </nav>
        <main ref={content} id="contenido" className="stage" tabIndex={-1}>
          <MapViewport visible={showMap} lang={lang} />
          <Outlet />
        </main>
      </div>
    </div>
  );
}
