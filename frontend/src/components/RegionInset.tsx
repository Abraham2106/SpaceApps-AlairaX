import { useEffect, useRef } from "react";
import { useCantons } from "../data/queries";
import { publicUrl } from "../lib/api";
import { guanacasteFeatures, type Position } from "../lib/geo";
import type { Zone } from "../lib/types";

// Geographic extent and size of the bundled NASA GIBS snapshot (EPSG:4326).
const [west, south, east, north] = [-86.42, 9.53, -84.65, 11.31];
const [width, height] = [900, 905];

export function RegionInset({ zone }: { zone?: Zone }) {
  const { data } = useCantons();
  const canvas = useRef<HTMLCanvasElement>(null);
  const latitude = zone?.latitude;
  const longitude = zone?.longitude;

  useEffect(() => {
    const ctx = canvas.current?.getContext("2d");
    if (!ctx) return;
    const project = ([x, y]: Position): Position => [
      (x - west) / (east - west) * width,
      (north - y) / (north - south) * height,
    ];
    ctx.clearRect(0, 0, width, height);
    for (const { geometry } of data ? guanacasteFeatures(data) : []) {
      ctx.beginPath();
      const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
      for (const polygon of polygons) {
        for (const ring of polygon) {
          ring.forEach((coordinate, point) => {
            const [x, y] = project(coordinate);
            if (point === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.closePath();
        }
      }
      ctx.strokeStyle = "#f2f8f4b0";
      ctx.lineWidth = 1.6;
      ctx.stroke();
    }
    if (longitude === undefined || latitude === undefined) return;
    if (longitude < west || longitude > east || latitude < south || latitude > north) return;
    const [x, y] = project([longitude, latitude]);
    ctx.beginPath();
    ctx.arc(x, y, 19, 0, Math.PI * 2);
    ctx.fillStyle = "#0d2c4770";
    ctx.fill();
    ctx.strokeStyle = "#bfe9fd";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fillStyle = "#f1fbff";
    ctx.fill();
  }, [data, latitude, longitude]);

  return (
    <>
      <img src={publicUrl("geo/guanacaste-modis-2024-03-12.jpg")} width={width} height={height} alt="" />
      <canvas ref={canvas} width={width} height={height} aria-hidden="true" />
    </>
  );
}
