import type { BasemapId } from "../../lib/types";
import {
  HLS_FIRST_DATE,
  HLS_MIN_ZOOM,
  IMAGERY_SOURCES,
  clampImageryDate,
  latestHlsDate,
  type ImagerySourceId,
} from "./catalog";

export type ImageryRequest = {
  basemap: BasemapId;
  zoom: number;
  date: string;
  /** Fuentes que fallaron al cargar teselas con la fecha actual. */
  failed?: ReadonlySet<ImagerySourceId>;
  now?: Date;
};

/** Por qué HLS no está en pantalla, cuando el zoom ya lo pediría. */
export type HlsStatus = "active" | "zoom" | "too_recent" | "before_mission" | "failed" | "not_applicable";

export type ImageryChoice = {
  /** Capas visibles, de abajo arriba. */
  layers: ImagerySourceId[];
  /** Fuente que domina la vista y que la ficha nombra primero. */
  primary: ImagerySourceId;
  /** Día citado en la ficha; null cuando el proveedor no publica fecha. */
  date: string | null;
  hls: HlsStatus;
  /** true cuando la vista NASA cayó a Esri porque MODIS no cargó. */
  fallback: boolean;
};

/**
 * Elige qué imágenes mostrar según la capa base, el zoom y la fecha.
 * Nunca cambia de proveedor sin que la ficha lo diga: `fallback` lo marca.
 */
export function selectSource({ basemap, zoom, date, failed = new Set(), now = new Date() }: ImageryRequest): ImageryChoice {
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
