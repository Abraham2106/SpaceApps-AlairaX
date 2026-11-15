import { describe, expect, it } from "vitest";
import {
  clampImageryDate,
  defaultImageryDate,
  formatGsd,
  formatImageryDate,
  gibsTileUrl,
  insideBox,
  isIsoDay,
  sentinelTileUrl,
  type DroneImage,
  type DroneLookup,
  type SentinelLookup,
  type SentinelScene,
  tileUrlFor,
  MODIS_FIRST_DATE,
} from "./catalog";
import { selectSource } from "./selectSource";

const NOW = new Date("2026-11-15T12:00:00Z");

describe("catálogo de imágenes", () => {
  it("la fecha por defecto es ayer en UTC", () => {
    expect(defaultImageryDate(NOW)).toBe("2026-11-14");
    expect(defaultImageryDate(new Date("2026-03-01T00:30:00Z"))).toBe("2026-02-28");
  });

  it("acota la fecha entre el primer día de MODIS y ayer", () => {
    expect(clampImageryDate("1999-01-01", NOW)).toBe(MODIS_FIRST_DATE);
    expect(clampImageryDate("2030-01-01", NOW)).toBe("2026-11-14");
    expect(clampImageryDate("2024-03-12", NOW)).toBe("2024-03-12");
    expect(clampImageryDate("no-es-fecha", NOW)).toBe("2026-11-14");
    expect(clampImageryDate("2026-02-30", NOW)).toBe("2026-11-14");
    expect(clampImageryDate(null, NOW)).toBe("2026-11-14");
  });

  it("valida días ISO reales", () => {
    expect(isIsoDay("2024-02-29")).toBe(true);
    expect(isIsoDay("2023-02-29")).toBe(false);
    expect(isIsoDay("2024-3-1")).toBe(false);
  });

  it("arma las URL de GIBS con y sin fecha", () => {
    expect(gibsTileUrl("L", "2026-11-14", "M", "jpg")).toBe(
      "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/L/default/2026-11-14/M/{z}/{y}/{x}.jpg",
    );
    expect(tileUrlFor("modis", "2026-11-14")).toContain("MODIS_Terra_CorrectedReflectance_TrueColor/default/2026-11-14/GoogleMapsCompatible_Level9/");
    expect(tileUrlFor("hls", "2026-11-01")).toContain("HLS_S30_Nadir_BRDF_Adjusted_Reflectance/default/2026-11-01/GoogleMapsCompatible_Level12/{z}/{y}/{x}.png");
    expect(tileUrlFor("marble", "2026-11-14")).toBe(
      "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
    );
  });

  it("formatea la fecha en UTC sin correrla un día", () => {
    expect(formatImageryDate("2026-11-14", "en")).toBe("Nov 14, 2026");
    expect(formatImageryDate("2026-01-01", "es")).toContain("2026");
  });

  it("la URL de MODIS ya no tiene la fecha fija de 2024", () => {
    expect(tileUrlFor("modis", defaultImageryDate(NOW))).not.toContain("2024-03-12");
  });
});

describe("selectSource", () => {
  it("Esri y Blue Marble no citan fecha", () => {
    expect(selectSource({ basemap: "satellite", zoom: 12, date: "2026-11-01", now: NOW })).toMatchObject({ layers: ["esri"], date: null, fallback: false });
    expect(selectSource({ basemap: "marble", zoom: 5, date: "2026-11-01", now: NOW })).toMatchObject({ layers: ["marble"], date: null });
  });

  it("con zoom bajo la vista NASA es solo MODIS", () => {
    expect(selectSource({ basemap: "modis", zoom: 8, date: "2026-11-01", now: NOW })).toMatchObject({ layers: ["modis"], primary: "modis", date: "2026-11-01", hls: "zoom" });
  });

  it("con zoom alto superpone HLS sobre MODIS", () => {
    expect(selectSource({ basemap: "modis", zoom: 10, date: "2026-11-01", now: NOW })).toMatchObject({ layers: ["modis", "hls"], primary: "hls", hls: "active" });
  });

  it("no pide HLS para fechas que GIBS aún no publica", () => {
    expect(selectSource({ basemap: "modis", zoom: 11, date: "2026-11-14", now: NOW })).toMatchObject({ layers: ["modis"], hls: "too_recent" });
  });

  it("no pide HLS antes de Sentinel-2", () => {
    expect(selectSource({ basemap: "modis", zoom: 11, date: "2012-05-01", now: NOW })).toMatchObject({ layers: ["modis"], hls: "before_mission" });
  });

  it("si HLS falla queda MODIS", () => {
    const choice = selectSource({ basemap: "modis", zoom: 11, date: "2026-11-01", failed: new Set(["hls"]), now: NOW });
    expect(choice).toMatchObject({ layers: ["modis"], hls: "failed", fallback: false });
  });

  it("si MODIS falla y no hay HLS cae a Esri y lo marca", () => {
    const choice = selectSource({ basemap: "modis", zoom: 8, date: "2026-11-01", failed: new Set(["modis"]), now: NOW });
    expect(choice).toMatchObject({ layers: ["esri"], primary: "esri", date: null, fallback: true });
  });

  it("acota una fecha fuera de rango antes de citarla", () => {
    expect(selectSource({ basemap: "modis", zoom: 6, date: "2099-01-01", now: NOW }).date).toBe("2026-11-14");
  });
});

const SCENE: SentinelScene = {
  id: "S2B_16PFS_20261024_0_L2A",
  date: "2026-10-24",
  datetime: "2026-10-24T16:21:40Z",
  cloudCover: 14.2,
  platform: "sentinel-2b",
  bbox: [-86.087966, 9.856993, -85.080838, 10.854112],
  attribution: "Contains modified Copernicus Sentinel data 2026",
};
const READY: SentinelLookup = { state: "ready", scene: SCENE, reason: null };
const nasa = (zoom: number, sentinel?: SentinelLookup, failed?: Set<"modis" | "hls" | "s2" | "esri" | "marble">) =>
  selectSource({ basemap: "modis", zoom, date: "2026-11-08", now: NOW, sentinel, failed });

describe("selectSource con Sentinel-2", () => {
  it("sin backend Sentinel-2 queda apagado y no cambia la vista NASA", () => {
    expect(nasa(11)).toMatchObject({ layers: ["modis", "hls"], primary: "hls", s2: "off", scene: null });
  });

  it("Esri nunca pide Sentinel-2", () => {
    expect(selectSource({ basemap: "satellite", zoom: 12, date: "2026-11-08", now: NOW, sentinel: READY })).toMatchObject({ layers: ["esri"], s2: "off", scene: null });
  });

  it("bajo zoom 11 no se muestra la escena", () => {
    expect(nasa(10, READY)).toMatchObject({ s2: "zoom", scene: null, primary: "hls" });
  });

  it("mientras busca lo dice y no inventa escena", () => {
    expect(nasa(11, { state: "loading" })).toMatchObject({ s2: "searching", scene: null });
  });

  it("sin escena despejada o fuera del área lo distingue", () => {
    expect(nasa(11, { state: "ready", scene: null, reason: "no_clear_scene" })).toMatchObject({ s2: "none", scene: null });
    expect(nasa(11, { state: "ready", scene: null, reason: "outside" })).toMatchObject({ s2: "outside", scene: null });
  });

  it("si la búsqueda o las teselas fallan queda la vista NASA", () => {
    expect(nasa(11, { state: "error" })).toMatchObject({ s2: "failed", scene: null, primary: "hls" });
    expect(nasa(12, READY, new Set(["s2"]))).toMatchObject({ s2: "failed", scene: null });
  });

  it("con escena encima de la vista NASA cita el día de la escena", () => {
    const choice = nasa(11, READY);
    expect(choice).toMatchObject({ s2: "active", primary: "s2", date: "2026-10-24", scene: SCENE });
    expect(choice.layers.at(-1)).toBe("s2");
  });
});

describe("teselas Sentinel-2", () => {
  it("arma la URL del backend sin doble barra", () => {
    expect(sentinelTileUrl("http://127.0.0.1:8000/", SCENE.id)).toBe("http://127.0.0.1:8000/imagery/tiles/S2B_16PFS_20261024_0_L2A/{z}/{x}/{y}");
  });

  it("sabe si el centro sigue dentro de la escena", () => {
    expect(insideBox(-85.44, 10.63, SCENE.bbox)).toBe(true);
    expect(insideBox(-84.9, 10.63, SCENE.bbox)).toBe(false);
  });
});

// Imagen de dron de Filadelfia tal como la devuelve el backend (snapshot de OAM del 15 nov 2026).
const FILADELFIA: DroneImage = {
  id: "6848b842064c0ea430648e5e",
  title: "Filadelfia",
  date: "2025-06-10",
  gsdM: 0.02473519905988008,
  provider: "CAOBA REAL ESTATE MEDIA",
  license: "CC-BY 4.0",
  bbox: [-85.552686, 10.447786, -85.551693, 10.448388],
  tiles: "https://titiler.hotosm.org/cog/tiles/WebMercatorQuad/{z}/{x}/{y}@1x.png?url=x",
};
const OLDER: DroneImage = { ...FILADELFIA, id: "older", date: "2022-07-17", provider: "WebODM" };
const DRONES: DroneLookup = { state: "ready", images: [FILADELFIA, OLDER] };
const IN_FILADELFIA = [-85.55219, 10.448087] as const;
const LIBERIA = [-85.44, 10.63] as const;

describe("selectSource con imágenes de dron", () => {
  const nasa = { basemap: "modis" as const, date: "2026-11-08", now: NOW };

  it("sin backend la capa de dron queda apagada", () => {
    const choice = selectSource({ ...nasa, zoom: 18, center: IN_FILADELFIA });
    expect(choice.oam).toBe("off");
    expect(choice.layers).not.toContain("oam");
  });

  it("en Filadelfia aparece la imagen de dron con su fecha y su autor", () => {
    const choice = selectSource({ ...nasa, zoom: 18, drones: DRONES, center: IN_FILADELFIA });
    expect(choice.oam).toBe("active");
    expect(choice.primary).toBe("oam");
    expect(choice.date).toBe("2025-06-10");
    expect(choice.drone?.provider).toBe("CAOBA REAL ESTATE MEDIA");
    expect(choice.layers.at(-1)).toBe("oam");
  });

  it("fuera de las huellas no aparece nada", () => {
    const choice = selectSource({ ...nasa, zoom: 18, drones: DRONES, center: LIBERIA });
    expect(choice.oam).toBe("none");
    expect(choice.drone).toBeNull();
    expect(choice.layers).not.toContain("oam");
    expect(choice.date).toBe("2026-11-08");
  });

  it("antes del zoom de detalle no se muestra aunque el centro esté en la huella", () => {
    const choice = selectSource({ ...nasa, zoom: 15.9, drones: DRONES, center: IN_FILADELFIA });
    expect(choice.oam).toBe("zoom");
    expect(choice.primary).not.toBe("oam");
  });

  it("dice si las huellas se están buscando o fallaron", () => {
    expect(selectSource({ ...nasa, zoom: 18, drones: { state: "loading" }, center: IN_FILADELFIA }).oam).toBe("searching");
    expect(selectSource({ ...nasa, zoom: 18, drones: { state: "error" }, center: IN_FILADELFIA }).oam).toBe("failed");
    expect(selectSource({ ...nasa, zoom: 18, drones: DRONES, center: IN_FILADELFIA, failed: new Set(["oam"]) }).oam).toBe("failed");
  });

  it("también va sobre Esri, pero nunca sobre Blue Marble", () => {
    const esri = selectSource({ ...nasa, basemap: "satellite", zoom: 18, drones: DRONES, center: IN_FILADELFIA });
    expect(esri.layers).toEqual(["esri", "oam"]);
    expect(esri.date).toBe("2025-06-10");
    const marble = selectSource({ ...nasa, basemap: "marble", zoom: 18, drones: DRONES, center: IN_FILADELFIA });
    expect(marble.oam).toBe("off");
  });

  it("si dos huellas se tocan gana la primera, la más reciente", () => {
    const choice = selectSource({ ...nasa, zoom: 18, drones: DRONES, center: IN_FILADELFIA });
    expect(choice.drone?.id).toBe(FILADELFIA.id);
  });

  it("escribe la resolución de dron en centímetros o dice que no hay dato", () => {
    expect(formatGsd(0.02473519905988008, "es")).toBe("2,5 cm");
    expect(formatGsd(0.05, "en")).toBe("5 cm");
    expect(formatGsd(null, "es")).toBeNull();
    expect(formatGsd(0, "es")).toBeNull();
  });
});
