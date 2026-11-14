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

  it("dibuja la malla solo dentro de Guanacaste", () => {
    const mesh = hexMesh(collection, 0.2, "coarse");
    expect(mesh.features.length).toBeGreaterThan(5);
    expect(mesh.features.length).toBeLessThan(80);
  });
});

describe("contrato", () => {
  it("valida los cuatro fixtures", () => {
    const catalog = fixtureScenarioFileSchema.parse(JSON.parse(readFileSync(new URL("data/scenarios.json", root), "utf8")));
    expect(catalog._mock).toBe(true);
    for (const scenario of catalog.scenarios) {
      const compare = compareResponseSchema.parse(JSON.parse(readFileSync(new URL(`data/${scenario.result_file}`, root), "utf8")));
      expect(compare._mock).toBe(true);
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
    expect(text).toContain("sin dato");
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

  it("separa el fixture de una corrida real", () => {
    expect(leadSentence("es", "Niño fuerte", "modeled_water_deficit_mm", 3, true)).toContain("fixture");
    expect(leadSentence("es", "Niño fuerte", "modeled_water_deficit_mm", 3, false)).toContain("API");
  });

  it("recuerda que 2026 no es análogo", () => {
    expect(comparisonSentence({ ...base, like2026: true })).toContain("2026 no entra");
  });
});
