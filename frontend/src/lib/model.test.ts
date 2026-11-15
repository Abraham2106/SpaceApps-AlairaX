import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { cantonAt, pointInGeometry, type CantonCollection } from "./geo";
import { hexMesh } from "./color";
import { comparisonSentence, leadSentence } from "./plain";
import { compareResponseSchema, fixtureScenarioFileSchema } from "./schemas";

const root = new URL("../../public/", import.meta.url);
const collection = JSON.parse(readFileSync(new URL("geo/cantons.geojson", root), "utf8")) as CantonCollection;

describe("cantones", () => {
  it("coloca el punto provisional dentro de Liberia", () => {
    const hit = cantonAt(-85.5, 10.55, collection);
    expect(hit?.properties.name).toBe("Liberia");
    expect(hit?.properties.guanacaste).toBe(true);
  });

  it("deja San José fuera de Guanacaste", () => {
    const hit = cantonAt(-84.08, 9.93, collection);
    expect(hit?.properties.guanacaste).toBe(false);
  });

  it("reconoce un cuadrado simple", () => {
    expect(
      pointInGeometry(-85.5, 10.5, {
        type: "Polygon",
        coordinates: [[[-86, 10], [-85, 10], [-85, 11], [-86, 11], [-86, 10]]],
      }),
    ).toBe(true);
    expect(
      pointInGeometry(-80, 10, {
        type: "Polygon",
        coordinates: [[[-86, 10], [-85, 10], [-85, 11], [-86, 11], [-86, 10]]],
      }),
    ).toBe(false);
  });

  it("la superficie de cantones cubre los 11 y no repite una sola demanda", () => {
    const surface = JSON.parse(readFileSync(new URL("data/canton-surface.json", root), "utf8")) as {
      _mock: boolean;
      sowing_dates_observed: boolean;
      cantons: Record<string, { _mock: boolean; sowing_dates_observed: boolean; water_demand_mm: number; soil: { status: string } }>;
    };
    const ids = collection.features.filter((feature) => feature.properties.guanacaste).map((feature) => feature.id);
    expect(surface._mock).toBe(false);
    expect(Object.keys(surface.cantons).sort()).toEqual([...ids].sort());
    expect(Object.values(surface.cantons).every((row) => row._mock === false && row.sowing_dates_observed === false && row.soil.status === "map")).toBe(true);
    const demands = Object.values(surface.cantons).map((row) => row.water_demand_mm);
    expect(new Set(demands).size).toBe(demands.length);
    expect(surface.sowing_dates_observed).toBe(false);
    const canas = surface.cantons.canas as {
      water_demand_mm: number;
      soil: { status: string; field_capacity_m3_m3?: number };
      station_check?: { difference_mm: number; study_mm: number; published_field_capacity_m3_m3: number };
    };
    expect(canas.soil.status).toBe("map");
    expect(canas.soil.field_capacity_m3_m3).not.toBe(0.4411);
    expect(canas.station_check).toMatchObject({ difference_mm: -7.52, study_mm: 416.53, published_field_capacity_m3_m3: 0.4411 });
  });

  it("registra la retención publicada de la estación sin usarla en la resta ni marcarla validada", () => {
    const check = JSON.parse(readFileSync(new URL("../../../datasets/processed/validation/canas-ucr-2014.json", import.meta.url), "utf8")) as {
      sowing_dates_observed: boolean;
      station: { latitude: number; longitude: number; elevation_m: number; validated: boolean };
      station_result: { water_demand_mm: number };
      difference_mm: number;
      acceptable: boolean;
      station_soil: {
        field_capacity_m3_m3: { rest_of_district_mollisols: number; north_vertisols: number };
        enters_water_demand: boolean;
        wilting_point_m3_m3: null;
        fao56_bucket_claimed: boolean;
        soilgrids_used_for_station_demand: boolean;
        liberia_soil_used_for_station_demand: boolean;
      };
    };
    expect(check.sowing_dates_observed).toBe(false);
    expect(check.station).toMatchObject({ latitude: 10.3197162, longitude: -85.1120922, elevation_m: 45, validated: false });
    expect(check.station_result.water_demand_mm).toBe(409.01);
    expect(check.difference_mm).toBe(-7.52);
    expect(Math.abs(check.difference_mm)).toBeLessThanOrEqual(157.64);
    expect(check.acceptable).toBe(true);
    expect(check.station_soil.field_capacity_m3_m3).toEqual({ rest_of_district_mollisols: 0.4411, north_vertisols: 0.6116 });
    expect(check.station_soil.enters_water_demand).toBe(false);
    expect(check.station_soil.wilting_point_m3_m3).toBeNull();
    expect(check.station_soil.fao56_bucket_claimed).toBe(false);
    expect(check.station_soil.soilgrids_used_for_station_demand).toBe(false);
    expect(check.station_soil.liberia_soil_used_for_station_demand).toBe(false);
  });

  it("dibuja la malla solo dentro de Guanacaste", () => {
    const mesh = hexMesh(collection, 0.2, "coarse");
    expect(mesh.features.length).toBeGreaterThan(5);
    expect(mesh.features.length).toBeLessThan(80);
  });
});

describe("contrato", () => {
  it("valida las cuatro comparaciones precalculadas del piloto", () => {
    const catalog = fixtureScenarioFileSchema.parse(JSON.parse(readFileSync(new URL("data/scenarios.json", root), "utf8")));
    expect(catalog._mock).toBe(false);
    expect(catalog.scenarios).toHaveLength(4);
    for (const scenario of catalog.scenarios) {
      const compare = compareResponseSchema.parse(JSON.parse(readFileSync(new URL(`data/${scenario.result_file}`, root), "utf8")));
      expect(compare._mock).toBe(false);
      expect(compare.zona.validated).toBe(false);
      expect(compare.rotations.every((rotation) => rotation.runs.every((run) => run.daily_balance.length >= 365))).toBe(true);
      expect(compare.analog_years.some((item) => item.year === 2026)).toBe(false);
      expect(compare.uncertainty_method).toBe("empirical_linear_quantiles_across_analog_years");
    }
  });
});

describe("lenguaje llano", () => {
  const base = {
    lang: "es" as const,
    scenarioName: "Niño fuerte",
    metric: "modeled_water_deficit_mm" as const,
    rotationName: "Arroz → sorgo",
    baselineName: "Arroz → melón",
    isBaseline: false,
    p50: 100,
    deltaP50: -20,
    n: 3,
    like2026: false,
  };

  it("describe el delta negativo sin declararlo ahorro ni ganador", () => {
    const text = comparisonSentence(base);
    expect(text).toContain("−20");
    expect(text).toContain("más bajo");
    expect(text).toContain("No es rendimiento");
    expect(text.toLowerCase()).not.toContain("la ganadora");
    expect(text.toLowerCase()).not.toContain("recomendamos");
  });

  it("no convierte un null en cero", () => {
    const text = comparisonSentence({ ...base, p50: null, deltaP50: null });
    expect(text).toBe("");
    expect(text).not.toMatch(/0 mm/);
  });

  it("explica el delta cero de la referencia", () => {
    const text = comparisonSentence({
      ...base,
      rotationName: "Arroz → melón",
      isBaseline: true,
      deltaP50: 0,
      p50: 120,
    });
    expect(text).toContain("referencia");
    expect(text).toContain("contra ella misma");
  });

  it("la lectura dice las medianas sin anunciar la procedencia", () => {
    const text = leadSentence("es", "Niño fuerte", "modeled_water_deficit_mm", 3);
    expect(text).toContain("medianas");
    expect(text.toLowerCase()).not.toContain("fixture");
    expect(text.toLowerCase()).not.toContain("estim");
  });

  it("recuerda que 2026 no es análogo", () => {
    expect(comparisonSentence({ ...base, like2026: true })).toContain("2026 no entra");
  });
});
