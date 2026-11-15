import type { Lang } from "../../lib/types";

// Catálogo de las imágenes de fondo del mapa. Cada fuente declara proveedor,
// producto, resolución y si publica fecha. Ninguna imagen se muestra sin esa ficha.

export type ImagerySourceId = "esri" | "modis" | "hls" | "s2" | "marble";

export type ImagerySource = {
  id: ImagerySourceId;
  /** Id de la fuente y de la capa en el estilo de MapLibre. */
  mapId: "satellite" | "modis" | "hls" | "s2" | "marble";
  provider: string;
  product: string;
  /** Resolución nominal en metros; null cuando el proveedor no la fija por tesela. */
  resolutionM: number | null;
  /** true cuando la tesela corresponde a un día concreto que se puede citar. */
  dated: boolean;
  maxzoom: number;
};

export const GIBS_BASE = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";

/** Primer día de MODIS Terra en GIBS. */
export const MODIS_FIRST_DATE = "2000-02-24";
/** Primer día de HLS S30 (Sentinel-2A armonizado). Antes de esa fecha no hay HLS. */
export const HLS_FIRST_DATE = "2015-11-28";
/**
 * Días que HLS tarda en llegar a GIBS. El 15 nov 2026 GetCapabilities daba como
 * última fecha el 7 nov 2026, ocho días antes. Con una fecha más reciente no se pide HLS.
 */
export const HLS_LATENCY_DAYS = 7;
/** Desde este zoom MODIS (250 m) ya se ve pixelado y se superpone HLS (30 m). */
export const HLS_MIN_ZOOM = 9;
/** Desde este zoom HLS (30 m) ya se ve pixelado y se pide la escena Sentinel-2 (10 m) al backend. */
export const S2_MIN_ZOOM = 11;
/** El backend solo corta teselas Sentinel-2 entre estos zooms. */
export const S2_TILE_ZOOM = { min: 9, max: 14 } as const;
/** Zona que el backend acepta para buscar escenas (Guanacaste con margen): oeste, sur, este, norte. */
export const S2_AREA = [-86.2, 9.4, -84.4, 11.4] as const;

export const IMAGERY_SOURCES: Record<ImagerySourceId, ImagerySource> = {
  esri: {
    id: "esri",
    mapId: "satellite",
    provider: "Esri World Imagery",
    product: "Esri, Maxar, Earthstar Geographics",
    resolutionM: null,
    dated: false,
    maxzoom: 19,
  },
  modis: {
    id: "modis",
    mapId: "modis",
    provider: "NASA GIBS",
    product: "MODIS Terra",
    resolutionM: 250,
    dated: true,
    maxzoom: 9,
  },
  hls: {
    id: "hls",
    mapId: "hls",
    provider: "NASA GIBS",
    product: "HLS Sentinel-2",
    resolutionM: 30,
    dated: true,
    maxzoom: 12,
  },
  s2: {
    id: "s2",
    mapId: "s2",
    provider: "Copernicus Sentinel-2",
    product: "Sentinel-2 L2A",
    resolutionM: 10,
    dated: true,
    maxzoom: S2_TILE_ZOOM.max,
  },
  marble: {
    id: "marble",
    mapId: "marble",
    provider: "NASA GIBS",
    product: "Blue Marble",
    resolutionM: 500,
    dated: false,
    maxzoom: 8,
  },
};

const GIBS_LAYERS = {
  modis: { layer: "MODIS_Terra_CorrectedReflectance_TrueColor", matrix: "GoogleMapsCompatible_Level9", ext: "jpg" },
  hls: { layer: "HLS_S30_Nadir_BRDF_Adjusted_Reflectance", matrix: "GoogleMapsCompatible_Level12", ext: "png" },
  marble: { layer: "BlueMarble_NextGeneration", matrix: "GoogleMapsCompatible_Level8", ext: "jpeg" },
} as const;

export function gibsTileUrl(layer: string, date: string | null, matrix: string, ext: string): string {
  // Las capas sin dimensión de tiempo (Blue Marble) no llevan segmento de fecha.
  const time = date ? `${date}/` : "";
  return `${GIBS_BASE}/${layer}/default/${time}${matrix}/{z}/{y}/{x}.${ext}`;
}

/** Plantilla de teselas de una fuente GIBS. Las fuentes sin fecha ignoran `date`. */
export function tileUrlFor(id: "modis" | "hls" | "marble", date: string): string {
  const spec = GIBS_LAYERS[id];
  return gibsTileUrl(spec.layer, id === "marble" ? null : date, spec.matrix, spec.ext);
}

/** Escena Sentinel-2 elegida por el backend para la vista: un solo día y un solo id. */
export type SentinelScene = {
  id: string;
  date: string;
  datetime: string;
  cloudCover: number | null;
  platform: string | null;
  /** Oeste, sur, este, norte en grados. */
  bbox: [number, number, number, number];
  attribution: string;
};

/** Qué sabe el mapa de la escena Sentinel-2 para la vista actual. */
export type SentinelLookup =
  | { state: "loading" }
  | { state: "ready"; scene: SentinelScene | null; reason: "no_clear_scene" | "outside" | null }
  | { state: "error" };

export function sentinelTileUrl(apiBase: string, sceneId: string): string {
  return `${apiBase.replace(/\/$/, "")}/imagery/tiles/${encodeURIComponent(sceneId)}/{z}/{x}/{y}`;
}

export function insideBox(lon: number, lat: number, box: readonly [number, number, number, number]): boolean {
  return lon >= box[0] && lon <= box[2] && lat >= box[1] && lat <= box[3];
}

export const ESRI_TILE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

function toIso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return toIso(date);
}

/** Ayer en UTC: el último día que GIBS suele tener completo. */
export function latestImageryDate(now: Date = new Date()): string {
  return addDays(toIso(now), -1);
}

export function defaultImageryDate(now: Date = new Date()): string {
  return latestImageryDate(now);
}

export function isIsoDay(value: string | null | undefined): value is string {
  if (!value || !ISO_DAY.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && toIso(parsed) === value;
}

/** Lleva cualquier valor a un día válido entre el primer día de MODIS y ayer. */
export function clampImageryDate(value: string | null | undefined, now: Date = new Date()): string {
  const latest = latestImageryDate(now);
  if (!isIsoDay(value)) return latest;
  if (value < MODIS_FIRST_DATE) return MODIS_FIRST_DATE;
  if (value > latest) return latest;
  return value;
}

/** Último día que se espera tener en HLS según la latencia medida. */
export function latestHlsDate(now: Date = new Date()): string {
  return addDays(toIso(now), -HLS_LATENCY_DAYS);
}

/** Fecha legible para la ficha y los créditos, sin desfase de zona horaria. */
export function formatImageryDate(iso: string, lang: Lang): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(lang === "es" ? "es-CR" : "en-US", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}
