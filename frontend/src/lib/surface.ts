import { useQuery } from "@tanstack/react-query";
import type maplibregl from "maplibre-gl";
import { z } from "zod";
import { publicUrl } from "./api";
import { cividis } from "./color";
import type { MetricId } from "./types";

const row = z.object({
  rice_melon: z.number(),
  rice_legume: z.number(),
  rice_sorghum: z.number(),
  delta_legume: z.number(),
  delta_sorghum: z.number(),
});

const surfaceSchema = z.object({
  _mock: z.literal(true),
  purpose: z.string(),
  warnings: z.array(z.string()),
  cantons: z.record(z.string(), z.object({
    _mock: z.literal(true),
    modeled_water_deficit_mm: row,
    crop_water_demand_mm: row,
    water_stress_days: row,
  })),
});

export type Surface = z.infer<typeof surfaceSchema>;
export type SurfaceRow = z.infer<typeof row>;

export function useSurface() {
  return useQuery({
    queryKey: ["canton-surface"],
    staleTime: Infinity,
    queryFn: async ({ signal }) => {
      const response = await fetch(publicUrl("data/canton-surface.json"), { signal });
      if (!response.ok) throw new Error("surface");
      return surfaceSchema.parse(await response.json());
    },
  });
}

export function surfaceValue(surface: Surface | undefined, cantonId: string | undefined, metric: MetricId): SurfaceRow | null {
  if (!surface || !cantonId) return null;
  return surface.cantons[cantonId]?.[metric] ?? null;
}

export function surfaceDomain(surface: Surface | undefined, metric: MetricId): [number, number] {
  if (!surface) return [0, 1];
  const values = Object.values(surface.cantons).map((entry) => entry[metric].rice_melon);
  if (values.length === 0) return [0, 1];
  const min = Math.min(...values);
  const max = Math.max(...values);
  return min === max ? [min - 1, max + 1] : [min, max];
}

/** Upper half of cividis: ochre to yellow, one sequence a farmer can read on a night map. */
export function surfaceColor(value: number, min: number, max: number): string {
  const t = (value - min) / (max - min || 1);
  return cividis(0.5 + Math.min(1, Math.max(0, t)) * 0.5);
}

function matchColor(key: "id" | "canton", surface: Surface | undefined, metric: MetricId) {
  if (!surface) return "#1c2823" as const;
  const [min, max] = surfaceDomain(surface, metric);
  const expression: unknown[] = ["match", ["get", key]];
  for (const [id, metrics] of Object.entries(surface.cantons)) {
    expression.push(id, surfaceColor(metrics[metric].rice_melon, min, max));
  }
  expression.push("#24302c");
  return expression as maplibregl.ExpressionSpecification;
}

function matchHeight(key: "id" | "canton", surface: Surface | undefined, metric: MetricId) {
  if (!surface) return 0;
  const [min, max] = surfaceDomain(surface, metric);
  const expression: unknown[] = ["match", ["get", key]];
  for (const [id, metrics] of Object.entries(surface.cantons)) {
    const t = (metrics[metric].rice_melon - min) / (max - min || 1);
    expression.push(id, Math.round(480 + t * 2600));
  }
  expression.push(0);
  return expression as maplibregl.ExpressionSpecification;
}

export function cantonPaint(surface: Surface | undefined, metric: MetricId) {
  return matchColor("id", surface, metric);
}

export function hexPaint(surface: Surface | undefined, metric: MetricId) {
  return matchColor("canton", surface, metric);
}

export function cantonHeight(surface: Surface | undefined, metric: MetricId) {
  return matchHeight("id", surface, metric);
}

export function hexHeight(surface: Surface | undefined, metric: MetricId) {
  return matchHeight("canton", surface, metric);
}
