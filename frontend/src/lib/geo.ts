export type Position = [number, number];
export type Ring = Position[];

export type Geometry =
  | { type: "Polygon"; coordinates: Ring[] }
  | { type: "MultiPolygon"; coordinates: Ring[][] };

export type CantonProps = {
  id: string;
  sourceName: string;
  name: string;
  guanacaste: boolean;
  tint: string;
  center: [number, number];
};

export type CantonFeature = {
  type: "Feature";
  id: string;
  properties: CantonProps;
  geometry: Geometry;
};

export type CantonCollection = {
  type: "FeatureCollection";
  features: CantonFeature[];
};

function inRing(lon: number, lat: number, ring: Ring): boolean {
  let inside = false;
  for (let i = 0; i < ring.length - 1; i += 1) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[i + 1];
    const crosses = (y1 > lat) !== (y2 > lat);
    if (!crosses) continue;
    const x = ((x2 - x1) * (lat - y1)) / (y2 - y1 || 1e-15) + x1;
    if (lon < x) inside = !inside;
  }
  return inside;
}

export function pointInGeometry(lon: number, lat: number, geometry: Geometry): boolean {
  if (geometry.type === "Polygon") {
    const [outer, ...holes] = geometry.coordinates;
    if (!outer || !inRing(lon, lat, outer)) return false;
    return !holes.some((hole) => inRing(lon, lat, hole));
  }
  return geometry.coordinates.some((polygon) => {
    const [outer, ...holes] = polygon;
    if (!outer || !inRing(lon, lat, outer)) return false;
    return !holes.some((hole) => inRing(lon, lat, hole));
  });
}

export function cantonAt(lon: number, lat: number, collection: CantonCollection): CantonFeature | null {
  return collection.features.find((feature) => pointInGeometry(lon, lat, feature.geometry)) ?? null;
}

export function guanacasteFeatures(collection: CantonCollection): CantonFeature[] {
  return collection.features.filter((feature) => feature.properties.guanacaste);
}

export function boundsOf(features: CantonFeature[]): [number, number, number, number] | null {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  const visit = (ring: Ring) => {
    for (const [x, y] of ring) {
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  };
  for (const feature of features) {
    const geometry = feature.geometry;
    if (geometry.type === "Polygon") geometry.coordinates.forEach(visit);
    else geometry.coordinates.forEach((polygon) => polygon.forEach(visit));
  }
  if (!Number.isFinite(minX)) return null;
  return [minX, minY, maxX, maxY];
}
