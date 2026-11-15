import type { BasemapId } from "../../lib/types";
import {
  HLS_FIRST_DATE,
  HLS_MIN_ZOOM,
  IMAGERY_SOURCES,
  S2_MIN_ZOOM,
  clampImageryDate,
  latestHlsDate,
  type ImagerySourceId,
  type SentinelLookup,
  type SentinelScene,
} from "./catalog";

export type ImageryRequest = {
  basemap: BasemapId;
  zoom: number;
  date: string;
  /** Fuentes que fallaron al cargar teselas con la fecha actual. */
  failed?: ReadonlySet<ImagerySourceId>;
  /** Búsqueda de escena Sentinel-2. Sin backend no se pasa y Sentinel-2 queda apagado. */
  sentinel?: SentinelLookup;
  now?: Date;
};

/** Por qué HLS no está en pantalla, cuando el zoom ya lo pediría. */
export type HlsStatus = "active" | "zoom" | "too_recent" | "before_mission" | "failed" | "not_applicable";

/** Por qué Sentinel-2 10 m está o no en pantalla. "off" = no hay backend o la capa base no es NASA. */
export type S2Status = "active" | "off" | "zoom" | "searching" | "none" | "outside" | "failed";

export type ImageryChoice = {
  /** Capas visibles, de abajo arriba. */
  layers: ImagerySourceId[];
  /** Fuente que domina la vista y que la ficha nombra primero. */
  primary: ImagerySourceId;
  /** Día citado en la ficha; null cuando el proveedor no publica fecha. */
  date: string | null;
  hls: HlsStatus;
  s2: S2Status;
  /** Escena citada cuando Sentinel-2 está en pantalla. */
  scene: SentinelScene | null;
  /** true cuando la vista NASA cayó a Esri porque MODIS no cargó. */
  fallback: boolean;
};

/**
 * Elige qué imágenes mostrar según la capa base, el zoom y la fecha.
 * Nunca cambia de proveedor sin que la ficha lo diga: `fallback` lo marca.
 */
export function selectSource(request: ImageryRequest): ImageryChoice {
  const base = selectNasaBase(request);
  if (request.basemap !== "modis") return { ...base, s2: "off", scene: null };
  const s2 = sentinelStatus(request);
  if (s2 !== "active" || request.sentinel?.state !== "ready" || !request.sentinel.scene) {
    return { ...base, s2, scene: null };
  }
  // La escena se cita con su propio día, que puede ser anterior al pedido.
  const scene = request.sentinel.scene;
  return { ...base, layers: [...base.layers, "s2"], primary: "s2", date: scene.date, s2, scene };
}

function sentinelStatus({ zoom, failed = new Set(), sentinel }: ImageryRequest): S2Status {
  if (!sentinel) return "off";
  if (zoom < S2_MIN_ZOOM) return "zoom";
  if (failed.has("s2") || sentinel.state === "error") return "failed";
  if (sentinel.state === "loading") return "searching";
  if (!sentinel.scene) return sentinel.reason === "outside" ? "outside" : "none";
  return "active";
}

function selectNasaBase({ basemap, zoom, date, failed = new Set(), now = new Date() }: ImageryRequest): Omit<ImageryChoice, "s2" | "scene"> {
  if (basemap === "satellite") {
    return { layers: ["esri"], primary: "esri", date: null, hls: "not_applicable", fallback: false };
  }
  if (basemap === "marble") {
    return { layers: ["marble"], primary: "marble", date: null, hls: "not_applicable", fallback: false };
  }
  const day = clampImageryDate(date, now);
  const hls: HlsStatus =
    zoom < HLS_MIN_ZOOM
      ? "zoom"
      : day < HLS_FIRST_DATE
        ? "before_mission"
        : day > latestHlsDate(now)
          ? "too_recent"
          : failed.has("hls")
            ? "failed"
            : "active";
  if (failed.has("modis")) {
    if (hls === "active") return { layers: ["hls"], primary: "hls", date: day, hls, fallback: false };
    return { layers: ["esri"], primary: "esri", date: null, hls, fallback: true };
  }
  if (hls === "active") return { layers: ["modis", "hls"], primary: "hls", date: day, hls, fallback: false };
  return { layers: ["modis"], primary: "modis", date: day, hls, fallback: false };
}

export function resolutionOf(id: ImagerySourceId): number | null {
  return IMAGERY_SOURCES[id].resolutionM;
}
