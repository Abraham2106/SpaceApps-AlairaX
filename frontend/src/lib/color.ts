import { boundsOf, guanacasteFeatures, pointInGeometry, type CantonCollection } from "./geo";

export type HexCollection = {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    properties: { res: "coarse" | "mid" | "fine"; canton: string };
    geometry: { type: "Polygon"; coordinates: [number, number][][] };
  }[];
};

function hexRing(cx: number, cy: number, radius: number): [number, number][] {
  const cos = Math.cos((cy * Math.PI) / 180) || 0.01;
  const ring: [number, number][] = [];
  for (let i = 0; i < 6; i += 1) {
    const angle = ((60 * i - 30) * Math.PI) / 180;
    ring.push([cx + (radius * Math.cos(angle)) / cos, cy + radius * Math.sin(angle)]);
  }
  ring.push(ring[0]);
  return ring;
}

export function hexMesh(collection: CantonCollection, radius: number, res: "coarse" | "mid" | "fine"): HexCollection {
  const features = guanacasteFeatures(collection);
  const bounds = boundsOf(features);
  if (!bounds || radius <= 0) return { type: "FeatureCollection", features: [] };
  const [minX, minY, maxX, maxY] = bounds;
  const midLat = (minY + maxY) / 2;
  const cos = Math.cos((midLat * Math.PI) / 180) || 0.01;
  const dx = Math.sqrt(3) * radius / cos;
  const dy = 1.5 * radius;
  const hexes: HexCollection["features"] = [];
  let row = 0;
  for (let y = minY - dy; y <= maxY + dy; y += dy) {
    const offset = row % 2 === 0 ? 0 : dx / 2;
    for (let x = minX - dx; x <= maxX + dx; x += dx) {
      const cx = x + offset;
      const cy = y;
      const owner = features.find((feature) => pointInGeometry(cx, cy, feature.geometry));
      if (!owner) continue;
      hexes.push({
        type: "Feature",
        properties: { res, canton: owner.id },
        geometry: { type: "Polygon", coordinates: [hexRing(cx, cy, radius)] },
      });
    }
    row += 1;
  }
  return { type: "FeatureCollection", features: hexes };
}

/** Six published cividis anchors. The mesh inherits each hex's canton value. */
const CIVIDIS = ["#00224e", "#3b496c", "#6a6e73", "#9a8756", "#d2b24a", "#fee838"];

function channel(hex: string, index: number): number {
  return Number.parseInt(hex.slice(1 + index * 2, 3 + index * 2), 16);
}

export function cividis(t: number): string {
  const clamped = Math.min(1, Math.max(0, t));
  const scaled = clamped * (CIVIDIS.length - 1);
  const low = Math.floor(scaled);
  const high = Math.min(CIVIDIS.length - 1, low + 1);
  const mix = scaled - low;
  const parts = [0, 1, 2].map((index) => {
    const value = Math.round(channel(CIVIDIS[low], index) * (1 - mix) + channel(CIVIDIS[high], index) * mix);
    return value.toString(16).padStart(2, "0");
  });
  return `#${parts.join("")}`;
}

const DOMAIN: Record<string, [number, number]> = {
  modeled_water_deficit_mm: [0, 250],
  crop_water_demand_mm: [0, 1200],
  water_stress_days: [0, 40],
};

export function metricColor(metric: string, value: number | null): string {
  if (value === null) return "#8d9390";
  const [min, max] = DOMAIN[metric] ?? [0, 1];
  return cividis((value - min) / (max - min || 1));
}

export function metricDomain(metric: string): [number, number] {
  return DOMAIN[metric] ?? [0, 1];
}
