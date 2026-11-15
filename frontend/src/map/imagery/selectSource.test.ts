import { describe, expect, it } from "vitest";
import {
  clampImageryDate,
  defaultImageryDate,
  formatImageryDate,
  gibsTileUrl,
  isIsoDay,
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
