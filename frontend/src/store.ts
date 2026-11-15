import { create } from "zustand";
import type { BasemapId, Lang, MetricId, ScenarioId, ThemeName } from "./lib/types";
import { METRIC_IDS, SCENARIO_IDS } from "./lib/types";

export type Overlays = {
  cantons: boolean;
  hex: boolean;
  terrain: boolean;
  plates: boolean;
  osm: boolean;
};

type LocationFix = {
  latitude: number;
  longitude: number;
  inside: boolean;
  cantonId: string | null;
  cantonName: string | null;
};

type Store = {
  scenarioId: ScenarioId;
  metric: MetricId;
  lang: Lang;
  theme: ThemeName;
  basemap: BasemapId;
  overlays: Overlays;
  selected: string[];
  yearA: number | null;
  yearB: number | null;
  apiBase: string;
  location: LocationFix | null;
  locationMessage: string | null;
  hovered: string | null;
  setScenario: (id: ScenarioId) => void;
  setMetric: (id: MetricId) => void;
  setLang: (lang: Lang) => void;
  setTheme: (theme: ThemeName) => void;
  setBasemap: (id: BasemapId) => void;
  toggleOverlay: (key: keyof Overlays) => void;
  toggleCanton: (id: string, extend: boolean) => void;
  selectOnly: (id: string) => void;
  setYears: (yearA: number | null, yearB: number | null) => void;
  setApiBase: (value: string) => void;
  setLocation: (value: LocationFix | null, message: string | null) => void;
  setHovered: (id: string | null) => void;
  hydrate: (params: URLSearchParams) => void;
  toParams: () => URLSearchParams;
};

function isScenario(value: string | null): value is ScenarioId {
  return Boolean(value && (SCENARIO_IDS as readonly string[]).includes(value));
}

function isMetric(value: string | null): value is MetricId {
  return Boolean(value && (METRIC_IDS as readonly string[]).includes(value));
}

const storedTheme = typeof localStorage !== "undefined" ? localStorage.getItem("nandaview-theme") : null;
const storedLang = typeof localStorage !== "undefined" ? localStorage.getItem("nandaview-lang") : null;
const contrast =
  typeof window !== "undefined" && window.matchMedia("(prefers-contrast: more)").matches;

export const useInstrument = create<Store>((set, get) => ({
  scenarioId: "strong_el_nino",
  metric: "modeled_water_deficit_mm",
  lang: storedLang === "en" ? "en" : "es",
  theme: storedTheme === "sun" || storedTheme === "night" ? storedTheme : contrast ? "sun" : "night",
  basemap: "satellite",
  overlays: { cantons: true, hex: false, terrain: true, plates: false, osm: true },
  selected: [],
  yearA: null,
  yearB: null,
  apiBase: (import.meta.env.VITE_API_URL ?? "").trim(),
  location: null,
  locationMessage: null,
  hovered: null,
  setScenario: (scenarioId) => set({ scenarioId, yearA: null, yearB: null }),
  setMetric: (metric) => set({ metric }),
  setLang: (lang) => {
    localStorage.setItem("nandaview-lang", lang);
    set({ lang });
  },
  setTheme: (theme) => {
    localStorage.setItem("nandaview-theme", theme);
    set({ theme });
  },
  setBasemap: (basemap) => set({ basemap }),
  toggleOverlay: (key) => set({ overlays: { ...get().overlays, [key]: !get().overlays[key] } }),
  toggleCanton: (id, extend) => {
    const current = get().selected;
    if (!extend) {
      set({ selected: current.length === 1 && current[0] === id ? [] : [id] });
      return;
    }
    set({ selected: current.includes(id) ? current.filter((item) => item !== id) : [...current, id] });
  },
  selectOnly: (id) => set({ selected: [id] }),
  setYears: (yearA, yearB) => set({ yearA, yearB }),
  setApiBase: (apiBase) => set({ apiBase: apiBase.trim() }),
  setLocation: (location, locationMessage) => set({ location, locationMessage }),
  setHovered: (hovered) => set({ hovered }),
  hydrate: (params) => {
    const scenario = params.get("e");
    const metric = params.get("m");
    const theme = params.get("t");
    const lang = params.get("l");
    const cantons = params.get("c");
    const yearA = params.get("ya");
    const yearB = params.get("yb");
    set({
      scenarioId: isScenario(scenario) ? scenario : get().scenarioId,
      metric: isMetric(metric) ? metric : get().metric,
      theme: theme === "sun" || theme === "night" ? theme : get().theme,
      lang: lang === "en" || lang === "es" ? lang : get().lang,
      selected: cantons ? cantons.split(",").filter(Boolean) : get().selected,
      yearA: yearA && Number.isFinite(Number(yearA)) ? Number(yearA) : get().yearA,
      yearB: yearB && Number.isFinite(Number(yearB)) ? Number(yearB) : get().yearB,
    });
  },
  toParams: () => {
    const state = get();
    const params = new URLSearchParams();
    params.set("e", state.scenarioId);
    params.set("m", state.metric);
    params.set("t", state.theme);
    params.set("l", state.lang);
    if (state.selected.length) params.set("c", state.selected.join(","));
    if (state.yearA) params.set("ya", String(state.yearA));
    if (state.yearB) params.set("yb", String(state.yearB));
    return params;
  },
}));
