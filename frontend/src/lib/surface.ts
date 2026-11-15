import { useQuery } from "@tanstack/react-query";
import type maplibregl from "maplibre-gl";
import { z } from "zod";
import { publicUrl } from "./api";

const soilSchema = z.object({
  status: z.enum(["map", "unavailable"]),
  field_capacity_m3_m3: z.number().optional(),
  wilting_point_m3_m3: z.number().optional(),
  source: z.string(),
  error: z.string().optional(),
});

const stationCheckSchema = z.object({
  water_demand_mm: z.number(),
  study_mm: z.number(),
  difference_mm: z.number(),
  senara_mean_m3_s: z.number(),
  published_field_capacity_m3_m3: z.number(),
});

const cantonSchema = z.object({
  _mock: z.literal(false),
  name: z.string(),
  latitude: z.number(),
  longitude: z.number(),
  elevation_m: z.number(),
  rain_mm: z.number(),
  et0_mm: z.number(),
  water_demand_mm: z.number(),
  days: z.number(),
  soil: soilSchema,
  sowing_dates_observed: z.literal(false),
  station_check: stationCheckSchema.optional(),
});

const surfaceSchema = z.object({
  _mock: z.literal(false),
  purpose: z.string(),
  sowing_dates_observed: z.literal(false),
  warnings: z.array(z.string()),
  cantons: z.record(z.string(), cantonSchema),
});

export type Surface = z.infer<typeof surfaceSchema>;
export type SurfaceCanton = z.infer<typeof cantonSchema>;

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

export function surfaceCanton(surface: Surface | undefined, cantonId: string | undefined): SurfaceCanton | null {
  if (!surface || !cantonId) return null;
  return surface.cantons[cantonId] ?? null;
}

export function surfaceDomain(surface: Surface | undefined): [number, number] {
  if (!surface) return [0, 1];
  const values = Object.values(surface.cantons).map((entry) => entry.water_demand_mm);
  if (values.length === 0) return [0, 1];
  const min = Math.min(...values);
  const max = Math.max(...values);
  return min === max ? [min - 1, max + 1] : [min, max];
}

const GREEN = ["#d8f3dc", "#95d5b2", "#52b788", "#2d6a4f", "#1b4332"];

function mixHex(from: string, to: string, t: number): string {
  const channel = (hex: string, index: number) => Number.parseInt(hex.slice(1 + index * 2, 3 + index * 2), 16);
  const parts = [0, 1, 2].map((index) => {
    const value = Math.round(channel(from, index) * (1 - t) + channel(to, index) * t);
    return value.toString(16).padStart(2, "0");
  });
  return `#${parts.join("")}`;
}

/** Light green to deep green. One sequence, readable over a bright satellite. */
export function surfaceColor(value: number, min: number, max: number): string {
  const t = Math.min(1, Math.max(0, (value - min) / (max - min || 1)));
  const scaled = t * (GREEN.length - 1);
  const low = Math.floor(scaled);
  const high = Math.min(GREEN.length - 1, low + 1);
  return mixHex(GREEN[low], GREEN[high], scaled - low);
}

export function hexPaint(surface: Surface | undefined) {
  if (!surface) return "#1c2823" as const;
  const [min, max] = surfaceDomain(surface);
  const expression: unknown[] = ["match", ["get", "canton"]];
  for (const [id, entry] of Object.entries(surface.cantons)) {
    expression.push(id, surfaceColor(entry.water_demand_mm, min, max));
  }
  expression.push("#24302c");
  return expression as maplibregl.ExpressionSpecification;
}

export function hexHeight(surface: Surface | undefined) {
  if (!surface) return 0;
  const [min, max] = surfaceDomain(surface);
  const expression: unknown[] = ["match", ["get", "canton"]];
  for (const [id, entry] of Object.entries(surface.cantons)) {
    const t = (entry.water_demand_mm - min) / (max - min || 1);
    expression.push(id, Math.round(480 + t * 2600));
  }
  expression.push(0);
  return expression as maplibregl.ExpressionSpecification;
}
