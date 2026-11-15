import { NavLink, Outlet, useLocation, useSearchParams } from "react-router-dom";
import { useEffect } from "react";
import { Droplets, Grid2x2, Leaf, Map, Moon, ShieldCheck, Sprout, SunMedium } from "lucide-react";
import { NandaMap } from "../map/NandaMap";
import { RadioGroup } from "./RadioGroup";
import { useComparison } from "../data/queries";
import { useInstrument } from "../store";

const LINKS = [
  { to: "/", label: ["Mapa", "Map"], icon: Map },
  { to: "/cantones", label: ["Cantones", "Cantons"], icon: Grid2x2 },
  { to: "/rotaciones", label: ["Rotaciones", "Rotations"], icon: Sprout },
  { to: "/temporada", label: ["Temporada", "Season"], icon: Droplets },
  { to: "/confianza", label: ["Confianza", "Trust"], icon: ShieldCheck },
];

export function Shell() {
  const lang = useInstrument((state) => state.lang);
  const theme = useInstrument((state) => state.theme);
  const setLang = useInstrument((state) => state.setLang);
  const setTheme = useInstrument((state) => state.setTheme);
  const scenarioId = useInstrument((state) => state.scenarioId);
  const selected = useInstrument((state) => state.selected);
  const yearA = useInstrument((state) => state.yearA);
  const yearB = useInstrument((state) => state.yearB);
  const setScenario = useInstrument((state) => state.setScenario);
  const metric = useInstrument((state) => state.metric);
  const setMetric = useInstrument((state) => state.setMetric);
  const apiBase = useInstrument((state) => state.apiBase);
  const hydrate = useInstrument((state) => state.hydrate);
  const toParams = useInstrument((state) => state.toParams);
  const comparison = useComparison();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const showMap = location.pathname === "/" || location.pathname.startsWith("/cantones");
  const spanish = lang === "es";

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
  }, [scenarioId, metric, theme, lang, selected, yearA, yearB, params, setParams, toParams]);

  const mock = comparison.data?.compare?._mock ?? comparison.data?.catalog.mock ?? true;
  const liveFailure = comparison.data?.mode === "live" && comparison.data.httpStatus !== 200;

  return (
    <div className="app">
      <a className="skip" href="#contenido">{spanish ? "Saltar al contenido" : "Skip to content"}</a>
      <header className="topbar">
        <NavLink className="brand" to={{ pathname: "/", search: params.toString() }}>
          <Leaf size={22} strokeWidth={1.5} aria-hidden />
          <span className="brand-name">
            <strong>NandaView</strong>
            <span>AlairaX</span>
          </span>
        </NavLink>
        <label className="only-mobile">
          <span className="kicker">{spanish ? "Escenario" : "Scenario"}</span>
          <select className="scenario-select" value={scenarioId} onChange={(event) => setScenario(event.target.value as typeof scenarioId)} aria-label={spanish ? "Escenario" : "Scenario"}>
            <option value="strong_el_nino">{spanish ? "Niño fuerte" : "Strong El Niño"}</option>
            <option value="neutral">{spanish ? "Neutro" : "Neutral"}</option>
            <option value="la_nina">{spanish ? "Niña" : "La Niña"}</option>
            <option value="like_2026">{spanish ? "Como 2026" : "Like 2026"}</option>
          </select>
        </label>
        <RadioGroup
          className="segment hide-mobile"
          label={spanish ? "Escenario" : "Scenario"}
          value={scenarioId}
          onChange={setScenario}
          options={[
            { value: "strong_el_nino", label: spanish ? "Niño fuerte" : "Strong El Niño" },
            { value: "neutral", label: spanish ? "Neutro" : "Neutral" },
            { value: "la_nina", label: spanish ? "Niña" : "La Niña" },
            { value: "like_2026", label: spanish ? "Como 2026" : "Like 2026" },
          ]}
        />
        <RadioGroup
          className="metric-tabs"
          label={spanish ? "Métrica" : "Metric"}
          value={metric}
          onChange={setMetric}
          options={[
            { value: "modeled_water_deficit_mm", label: spanish ? "Agua" : "Water" },
            { value: "crop_water_demand_mm", label: spanish ? "Demanda" : "Demand" },
            { value: "water_stress_days", label: spanish ? "Estrés" : "Stress" },
          ]}
        />
        <span className="spacer" />
        {mock && !liveFailure ? (
          <p className="chip" role="status">
            <strong>{spanish ? "PRUEBA" : "SAMPLE"}</strong>
            <span className="chip-note">{spanish ? "Datos sintéticos" : "Synthetic data"}</span>
          </p>
        ) : null}
        {liveFailure ? (
          <p className="chip chip-live" role="status">
            <strong>HTTP {comparison.data?.httpStatus}</strong>
            <span>{comparison.data?.httpDetail}</span>
          </p>
        ) : null}
        <span className="mode-pill">{apiBase ? "API" : spanish ? "Fixture" : "Fixture"}</span>
        <button onClick={() => setTheme(theme === "night" ? "sun" : "night")} aria-pressed={theme === "sun"}>
          {theme === "night" ? <Moon size={16} aria-hidden /> : <SunMedium size={16} aria-hidden />}
          <span className="btn-label">{theme === "night" ? (spanish ? "Noche" : "Night") : (spanish ? "Sol" : "Sun")}</span>
        </button>
        <button onClick={() => setLang(spanish ? "en" : "es")}>{spanish ? "EN" : "ES"}</button>
      </header>
      <div className="workspace">
        <nav className="rail" aria-label={spanish ? "Secciones" : "Sections"}>
          {LINKS.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink key={link.to} to={{ pathname: link.to, search: params.toString() }} end={link.to === "/"}>
                <Icon size={18} strokeWidth={1.5} aria-hidden />
                <span className="rail-label">{spanish ? link.label[0] : link.label[1]}</span>
              </NavLink>
            );
          })}
        </nav>
        <main id="contenido" className="stage">
          <NandaMap hidden={!showMap} inset={location.pathname === "/" ? "panel" : "open"} />
          <Outlet />
        </main>
      </div>
    </div>
  );
}
