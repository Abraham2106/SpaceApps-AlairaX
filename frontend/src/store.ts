import { create } from "zustand";
import type { BasemapId, Lang, MetricId, ScenarioId, ThemeName } from "./lib/types";
import { METRIC_IDS, SCENARIO_IDS } from "./lib/types";
import type { LocalizedMessage } from "./lib/i18n";
import { clampImageryDate, defaultImageryDate, isIsoDay } from "./map/imagery/catalog";

export function isCantonBoundaryMessage(message: LocalizedMessage | null): message is LocalizedMessage & {
  key: "mapReading.noSimulationAvailable" | "nandaMap.noSimulationAvailableModelStays";
} {
  return message?.key === "mapReading.noSimulationAvailable" || message?.key === "nandaMap.noSimulationAvailableModelStays";
}

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
  /** Día de las imágenes NASA (MODIS y HLS), AAAA-MM-DD. Independiente del reproductor de temporada. */
  imageryDate: string;
  overlays: Overlays;
  selected: string[];
  selectedCenter: [number, number] | null;
  yearA: number | null;
  yearB: number | null;
  apiBase: string;
  location: LocationFix | null;
  locationMessage: LocalizedMessage | null;
  hovered: string | null;
  setScenario: (id: ScenarioId) => void;
  setMetric: (id: MetricId) => void;
  setLang: (lang: Lang) => void;
  setTheme: (theme: ThemeName) => void;
  setBasemap: (id: BasemapId) => void;
  setImageryDate: (value: string) => void;
  toggleOverlay: (key: keyof Overlays) => void;
  toggleCanton: (id: string, extend: boolean) => void;
  selectOnly: (id: string, center?: [number, number]) => void;
  setYears: (yearA: number | null, yearB: number | null) => void;
  setApiBase: (value: string) => void;
  setLocation: (value: LocationFix | null, message: LocalizedMessage | null) => void;
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

const storedLang = typeof localStorage !== "undefined" ? localStorage.getItem("nandaview-lang") : null;

export const useInstrument = create<Store>((set, get) => ({
  scenarioId: "strong_el_nino",
  metric: "modeled_water_deficit_mm",
  lang: storedLang === "en" ? "en" : "es",
  theme: "sun",
  basemap: "satellite",
  imageryDate: defaultImageryDate(),
  overlays: { cantons: true, hex: false, terrain: true, plates: false, osm: true },
  selected: [],
  selectedCenter: null,
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
  setImageryDate: (value) => set({ imageryDate: clampImageryDate(value) }),
  toggleOverlay: (key) => set({ overlays: { ...get().overlays, [key]: !get().overlays[key] } }),
  toggleCanton: (id, extend) => {
    const current = get().selected;
    const previousMessage = get().locationMessage;
    const locationMessage = isCantonBoundaryMessage(previousMessage) ? null : previousMessage;
    if (!extend) {
      set({ selected: current.length === 1 && current[0] === id ? [] : [id], selectedCenter: null, locationMessage });
      return;
    }
    set({ selected: current.includes(id) ? current.filter((item) => item !== id) : [...current, id], selectedCenter: null, locationMessage });
  },
  selectOnly: (id, center) => {
    const message = get().locationMessage;
    set({ selected: [id], selectedCenter: center ?? null, locationMessage: isCantonBoundaryMessage(message) ? null : message });
  },
  setYears: (yearA, yearB) => set({ yearA, yearB }),
  setApiBase: (apiBase) => set({ apiBase: apiBase.trim() }),
  setLocation: (location, locationMessage) => set({ location, locationMessage }),
  setHovered: (hovered) => set({ hovered }),
  hydrate: (params) => {
    const scenario = params.get("e");
    const metric = params.get("m");
    const lang = params.get("l");
    const cantons = params.get("c");
    const yearA = params.get("ya");
    const yearB = params.get("yb");
    const basemap = params.get("s");
    const imageryDate = params.get("i");
    set({
      basemap: basemap === "satellite" || basemap === "modis" || basemap === "marble" ? basemap : get().basemap,
      imageryDate: isIsoDay(imageryDate) ? clampImageryDate(imageryDate) : get().imageryDate,
      scenarioId: isScenario(scenario) ? scenario : get().scenarioId,
      metric: isMetric(metric) ? metric : get().metric,
      theme: "sun",
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
    if (state.basemap !== "satellite") params.set("s", state.basemap);
    if (state.basemap === "modis" && state.imageryDate !== defaultImageryDate()) params.set("i", state.imageryDate);
    return params;
  },
}));
