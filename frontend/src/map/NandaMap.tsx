import { translate } from "../lib/i18n";
import { useEffect, useRef, useState } from "react";
import maplibregl, { type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { hexMesh } from "../lib/color";
import { boundsOf, cantonAt, guanacasteFeatures } from "../lib/geo";
import { useCantons, useComparison } from "../data/queries";
import { formatValue } from "../lib/format";
import { hexHeight, hexPaint, surfaceValue, useSurface } from "../lib/surface";
import { useInstrument } from "../store";
import type { MetricId } from "../lib/types";
import { isMobile, isTablet } from "../lib/viewport";

const EMPTY = { type: "FeatureCollection" as const, features: [] };

function buildStyle(): StyleSpecification {
  const motion = reducedMotion() ? 0 : 680;
  return {
    version: 8,
    glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
    sources: {
      satellite: {
        type: "raster",
        tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
        tileSize: 256,
        maxzoom: 19,
      },
      modis: {
        type: "raster",
        tiles: [
          "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/2024-03-12/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg",
        ],
        tileSize: 256,
        maxzoom: 9,
      },
      marble: {
        type: "raster",
        tiles: [
          "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
        ],
        tileSize: 256,
        maxzoom: 8,
      },
      dem: {
        type: "raster-dem",
        tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
        encoding: "terrarium",
        tileSize: 256,
        maxzoom: 12,
      },
      openmaptiles: { type: "vector", url: "https://tiles.openfreemap.org/planet" },
      cantons: { type: "geojson", data: EMPTY },
      labels: { type: "geojson", data: EMPTY },
      hexCoarse: { type: "geojson", data: EMPTY },
      hexMid: { type: "geojson", data: EMPTY },
      hexFine: { type: "geojson", data: EMPTY },
      marks: { type: "geojson", data: EMPTY },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#0c1412" } },
      {
        id: "satellite",
        type: "raster",
        source: "satellite",
        paint: {
          "raster-saturation": -0.08,
          "raster-brightness-max": 0.95,
          "raster-brightness-min": 0.22,
          "raster-contrast": 0.06,
          "raster-opacity": 1,
        },
      },
      { id: "modis", type: "raster", source: "modis", layout: { visibility: "none" } },
      { id: "marble", type: "raster", source: "marble", layout: { visibility: "none" } },
      {
        id: "hillshade",
        type: "hillshade",
        source: "dem",
        paint: {
          "hillshade-exaggeration": 0.22,
          "hillshade-illumination-direction": 315,
          "hillshade-shadow-color": "#1a120c",
          "hillshade-highlight-color": "#fff3d4",
          "hillshade-accent-color": "#c4a574",
        },
      },
      {
        id: "canton-fill",
        type: "fill",
        source: "cantons",
        paint: {
          "fill-color": "#1c2823",
          "fill-color-transition": { duration: motion, delay: 0 },
          "fill-opacity-transition": { duration: motion, delay: 0 },
          "fill-opacity": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            0.34,
            ["boolean", ["feature-state", "hover"], false],
            0.26,
            ["get", "guanacaste"],
            0.04,
            0,
          ],
        },
      },
      {
        id: "canton-extrude",
        type: "fill-extrusion",
        source: "cantons",
        layout: { visibility: "none" },
        paint: {
          "fill-extrusion-color": ["get", "tint"],
          "fill-extrusion-height": ["case", ["get", "guanacaste"], 700, 0],
          "fill-extrusion-opacity": 0.72,
        },
      },
      ...(["coarse", "mid", "fine"] as const).flatMap((res) => {
        const source = res === "coarse" ? "hexCoarse" : res === "mid" ? "hexMid" : "hexFine";
        return [
          {
            id: `hex-${res}`,
            type: "fill" as const,
            source,
            layout: { visibility: "none" as const },
            paint: {
              "fill-color": "#9a8756",
              "fill-color-transition": { duration: motion, delay: 0 },
              "fill-opacity": 0.78,
            },
          },
          {
            id: `hex-${res}-extrude`,
            type: "fill-extrusion" as const,
            source,
            layout: { visibility: "none" as const },
            paint: {
              "fill-extrusion-color": "#9a8756",
              "fill-extrusion-color-transition": { duration: motion, delay: 0 },
              "fill-extrusion-height": 500,
              "fill-extrusion-opacity": 0.86,
            },
          },
        ];
      }),
      {
        id: "canton-casing",
        type: "line",
        source: "cantons",
        paint: {
          "line-color": "#06110e",
          "line-width": 0,
          "line-opacity": 0,
        },
      },
      {
        id: "canton-edge",
        type: "line",
        source: "cantons",
        paint: {
          "line-color": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            "#ffffff",
            ["boolean", ["feature-state", "hover"], false],
            "#d8f3dc",
            ["get", "guanacaste"],
            "rgba(244,247,242,0.9)",
            "rgba(244,247,242,0.28)",
          ],
          "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 2.4, ["boolean", ["feature-state", "hover"], false], 2, ["get", "guanacaste"], 1.6, 0.6],
          "line-opacity": ["case", ["get", "guanacaste"], 0.95, 0.55],
        },
      },
      {
        id: "canton-label",
        type: "symbol",
        source: "labels",
        layout: {
          "text-field": ["get", "name"],
          "text-font": ["Noto Sans Regular"],
          "text-size": ["interpolate", ["linear"], ["zoom"], 6, 11, 10, 14],
          "text-letter-spacing": 0.04,
        },
        paint: {
          "text-color": "#f4f7f2",
          "text-halo-color": "#06110e",
          "text-halo-width": 1.8,
          "text-halo-blur": 0.4,
        },
      },
      {
        id: "osm-roads",
        type: "line",
        source: "openmaptiles",
        "source-layer": "transportation",
        minzoom: 11,
        filter: ["match", ["get", "class"], ["motorway", "trunk", "primary", "secondary"], true, false],
        paint: {
          "line-color": "rgba(255, 248, 236, 0.55)",
          "line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.4, 14, 2],
        },
      },
      {
        id: "osm-places",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "place",
        minzoom: 11,
        filter: ["match", ["get", "class"], ["city", "town"], true, false],
        layout: {
          "text-field": ["coalesce", ["get", "name:es"], ["get", "name_es"], ["get", "name:latin"], ["get", "name"]],
          "text-font": ["Noto Sans Regular"],
          "text-size": 12,
        },
        paint: {
          "text-color": "#f7f4ec",
          "text-halo-color": "#07110e",
          "text-halo-width": 1.2,
        },
      },
      {
        id: "model-point",
        type: "circle",
        source: "marks",
        filter: ["==", ["get", "kind"], "model"],
        paint: {
          "circle-radius": 5,
          "circle-color": "rgba(0,0,0,0)",
          "circle-stroke-color": "#e7eef4",
          "circle-stroke-width": 1.5,
        },
      },
      {
        id: "user-point",
        type: "circle",
        source: "marks",
        filter: ["==", ["get", "kind"], "user"],
        paint: {
          "circle-radius": 7,
          "circle-color": "#f4efe4",
          "circle-stroke-color": "#143d66",
          "circle-stroke-width": 2,
        },
      },
      {
        id: "model-label",
        type: "symbol",
        source: "marks",
        filter: ["==", ["get", "kind"], "model"],
        layout: {
          "text-field": ["get", "label"],
          "text-font": ["Noto Sans Regular"],
          "text-size": 12,
          "text-offset": [0, 1.15],
          "text-anchor": "top",
        },
        paint: {
          "text-color": "#f4f7f2",
          "text-halo-color": "#06110e",
          "text-halo-width": 1.6,
        },
      },
    ],
  };
}

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function NandaMap({ hidden, inset }: { hidden: boolean; inset: "panel" | "open" }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const ready = useRef(false);
  const hovered = useRef<string | null>(null);
  const platesWere = useRef(false);
  const surfaceRef = useRef<ReturnType<typeof useSurface>["data"]>(undefined);
  const metricRef = useRef<MetricId>("modeled_water_deficit_mm");
  const [tip, setTip] = useState<{ x: number; y: number; name: string; value: number | null; outside: boolean } | null>(null);
  const cantons = useCantons();
  const comparison = useComparison();
  const surface = useSurface();
  const basemap = useInstrument((state) => state.basemap);
  const overlays = useInstrument((state) => state.overlays);
  const selected = useInstrument((state) => state.selected);
  const selectedCenter = useInstrument((state) => state.selectedCenter);
  const metric = useInstrument((state) => state.metric);
  const lang = useInstrument((state) => state.lang);
  const location = useInstrument((state) => state.location);
  const toggleCanton = useInstrument((state) => state.toggleCanton);
  const setLocation = useInstrument((state) => state.setLocation);
  useEffect(() => {
    surfaceRef.current = surface.data;
    metricRef.current = metric;
  }, [surface.data, metric]);

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: buildStyle(),
      center: [-85.45, 10.45],
      zoom: 8.05,
      pitch: 0,
      bearing: 0,
      maxPitch: 52,
      attributionControl: false,
      fadeDuration: reducedMotion() ? 0 : 280,
    });
    mapRef.current = map;
    map.on("load", () => {
      ready.current = true;
      map.setTerrain(null);
    });
    const cantonLayers = ["canton-fill", "canton-extrude"];
    map.on("click", cantonLayers, (event) => {
      const feature = event.features?.[0];
      if (!feature) return;
      const guanacaste = Boolean(feature.properties.guanacaste);
      const id = String(feature.id ?? feature.properties.id);
      if (!guanacaste) {
        setLocation(useInstrument.getState().location, {
          key: "nandaMap.noSimulationAvailableModelStays",
          values: { canton: feature.properties.name },
        });
        return;
      }
      toggleCanton(id, event.originalEvent.shiftKey);
    });
    map.on("mousemove", cantonLayers, (event) => {
      map.getCanvas().style.cursor = "pointer";
      const id = event.features?.[0]?.id;
      if (id == null) return;
      const next = String(id);
      if (hovered.current && hovered.current !== next) {
        map.setFeatureState({ source: "cantons", id: hovered.current }, { hover: false });
      }
      hovered.current = next;
      map.setFeatureState({ source: "cantons", id: next }, { hover: true });
      const feature = event.features?.[0];
      const name = String(feature?.properties.name ?? "");
      const inside = Boolean(feature?.properties.guanacaste);
      const row = inside ? surfaceValue(surfaceRef.current, next, metricRef.current) : null;
      useInstrument.getState().setHovered(next);
      setTip({
        x: event.point.x,
        y: event.point.y,
        name,
        value: row ? row.rice_melon : null,
        outside: !inside,
      });
    });
    map.on("mouseleave", cantonLayers, () => {
      map.getCanvas().style.cursor = "";
      if (hovered.current) map.setFeatureState({ source: "cantons", id: hovered.current }, { hover: false });
      hovered.current = null;
      useInstrument.getState().setHovered(null);
      setTip(null);
    });
    const onResize = () => map.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      map.remove();
      mapRef.current = null;
      ready.current = false;
    };
  }, [setLocation, toggleCanton]);

  useEffect(() => {
    const canvas = mapRef.current?.getCanvas();
    canvas?.setAttribute("role", "application");
    canvas?.setAttribute("aria-label", translate(lang, "nandaMap.mapCostaRicaArrowKeys"));
  }, [lang]);

  useEffect(() => {
    const map = mapRef.current;
    const collection = cantons.data;
    if (!map || !collection) return;
    const apply = () => {
      (map.getSource("cantons") as maplibregl.GeoJSONSource | undefined)?.setData(collection);
      (map.getSource("labels") as maplibregl.GeoJSONSource | undefined)?.setData({
        type: "FeatureCollection",
        features: collection.features
          .filter((feature) => feature.properties.guanacaste)
          .map((feature) => ({
            type: "Feature" as const,
            properties: { name: feature.properties.name },
            geometry: { type: "Point" as const, coordinates: feature.properties.center },
          })),
      });
      (map.getSource("hexCoarse") as maplibregl.GeoJSONSource | undefined)?.setData(hexMesh(collection, 0.22, "coarse"));
      (map.getSource("hexMid") as maplibregl.GeoJSONSource | undefined)?.setData(hexMesh(collection, 0.12, "mid"));
      (map.getSource("hexFine") as maplibregl.GeoJSONSource | undefined)?.setData(hexMesh(collection, 0.065, "fine"));
      if (useInstrument.getState().selected.length === 0) {
        const bounds = boundsOf(guanacasteFeatures(collection));
        if (bounds) {
          const narrow = isMobile();
          map.fitBounds(
            [[bounds[0], bounds[1]], [bounds[2], bounds[3]]],
            {
              padding: narrow
                ? { top: 36, bottom: 150, left: 10, right: 10 }
                : isTablet() && inset === "panel"
                  ? { top: 86, bottom: 80, left: 290, right: 24 }
                  : inset === "panel"
                  ? { top: 24, bottom: 72, left: 368, right: 96 }
                  : { top: 36, bottom: 64, left: 120, right: 56 },
              pitch: 0,
              bearing: 0,
              duration: reducedMotion() ? 0 : 900,
              maxZoom: 8.8,
            },
          );
        }
      }
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [cantons.data, inset]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      for (const id of ["satellite", "modis", "marble"] as const) {
        map.setLayoutProperty(id, "visibility", basemap === id ? "visible" : "none");
      }
      map.setLayoutProperty("canton-fill", "visibility", overlays.cantons && !overlays.plates ? "visible" : "none");
      map.setLayoutProperty("canton-casing", "visibility", overlays.cantons ? "visible" : "none");
      map.setLayoutProperty("canton-edge", "visibility", overlays.cantons ? "visible" : "none");
      map.setLayoutProperty("canton-label", "visibility", overlays.cantons ? "visible" : "none");
      map.setLayoutProperty("canton-extrude", "visibility", overlays.cantons && overlays.plates ? "visible" : "none");
      map.setLayoutProperty("osm-roads", "visibility", overlays.osm ? "visible" : "none");
      map.setLayoutProperty("osm-places", "visibility", overlays.osm ? "visible" : "none");
      const mesh = hexPaint(surface.data, metric);
      map.setLayoutProperty("hillshade", "visibility", overlays.terrain ? "visible" : "none");
      map.setTerrain(null);
      const zoom = map.getZoom();
      const level = zoom < 8.2 ? "coarse" : zoom < 10 ? "mid" : "fine";
      for (const res of ["coarse", "mid", "fine"]) {
        const show = overlays.hex && res === level;
        map.setLayoutProperty(`hex-${res}`, "visibility", show && !overlays.plates ? "visible" : "none");
        map.setLayoutProperty(`hex-${res}-extrude`, "visibility", show && overlays.plates ? "visible" : "none");
        map.setPaintProperty(`hex-${res}`, "fill-color", mesh);
        map.setPaintProperty(`hex-${res}-extrude`, "fill-extrusion-color", mesh);
        map.setPaintProperty(`hex-${res}-extrude`, "fill-extrusion-height", hexHeight(surface.data, metric));
      }
      if (overlays.plates && !platesWere.current && map.getPitch() < 24) {
        map.easeTo({ pitch: 42, bearing: -16, duration: reducedMotion() ? 0 : 900 });
      }
      if (!overlays.plates && platesWere.current) {
        map.easeTo({ pitch: 0, bearing: 0, duration: reducedMotion() ? 0 : 700 });
      }
      platesWere.current = overlays.plates;
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
    map.on("zoomend", apply);
    return () => {
      map.off("zoomend", apply);
    };
  }, [basemap, overlays, metric, surface.data]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const syncSelection = () => {
      for (const feature of cantons.data?.features ?? []) {
        map.setFeatureState({ source: "cantons", id: feature.id }, { selected: selected.includes(feature.id) });
      }
      if (selected.length !== 1) return;
      const feature = cantons.data?.features.find((item) => item.id === selected[0]);
      if (!feature) return;
      map.flyTo({
        center: selectedCenter ?? feature.properties.center,
        zoom: 9.6,
        pitch: 26,
        bearing: -14,
        duration: reducedMotion() ? 0 : 1700,
        curve: 1.35,
        essential: true,
        padding: isMobile()
          ? { top: 30, bottom: 200, left: 16, right: 72 }
          : isTablet() ? { left: 290, right: 24, top: 86, bottom: 80 } : { left: 430, right: 96, top: 24, bottom: 80 },
      });
    };
    if (ready.current) syncSelection();
    else map.once("load", syncSelection);
    return () => { map.off("load", syncSelection); };
  }, [selected, selectedCenter, cantons.data]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const zona = comparison.data?.compare?.zona ?? comparison.data?.catalog.zona;
    const features: { type: "Feature"; properties: { kind: string; label?: string }; geometry: { type: "Point"; coordinates: [number, number] } }[] = [];
    if (zona) {
      features.push({
        type: "Feature" as const,
        properties: {
          kind: "model",
          label: (() => {
            const place = cantons.data && zona ? cantonAt(zona.longitude, zona.latitude, cantons.data)?.properties.name : "";
            return place ? `punto · ${place}` : "punto";
          })(),
        },
        geometry: { type: "Point" as const, coordinates: [zona.longitude, zona.latitude] },
      });
    }
    if (location) {
      features.push({
        type: "Feature" as const,
        properties: { kind: "user" },
        geometry: { type: "Point" as const, coordinates: [location.longitude, location.latitude] },
      });
    }
    const apply = () => (map.getSource("marks") as maplibregl.GeoJSONSource | undefined)?.setData({ type: "FeatureCollection", features });
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [comparison.data, location, metric, cantons.data]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !location) return;
    map.flyTo({
      center: [location.longitude, location.latitude],
      zoom: Math.max(map.getZoom(), 10),
      pitch: 24,
      bearing: 12,
      duration: reducedMotion() ? 0 : 1800,
      curve: 1.4,
      essential: true,
    });
  }, [location]);

  useEffect(() => {
    if (!hidden) mapRef.current?.resize();
  }, [hidden]);

  const zona = comparison.data?.compare?.zona ?? comparison.data?.catalog.zona;
  const pointName = zona && cantons.data ? cantonAt(zona.longitude, zona.latitude, cantons.data)?.properties.name : null;
  const coordinates = zona ? `${zona.latitude.toFixed(2)}, ${zona.longitude.toFixed(2)}` : "…";
  const credit = translate(lang, "nandaMap.credit", {
    imagery: translate(lang, `nandaMap.${basemap}Credit`),
    roads: overlays.osm ? translate(lang, "nandaMap.roadCredit") : "",
    point: pointName ? translate(lang, "nandaMap.pointCredit", { canton: pointName }) : "",
    coordinates,
  });
  const shortCredit = translate(lang, "nandaMap.sourcesPoint", { value: coordinates });
  const tipValue = tip
    ? tip.outside
      ? (translate(lang, "nandaMap.noSimulationAvailable"))
      : tip.value == null
        ? (translate(lang, "common.noData"))
        : formatValue(tip.value, metric, lang)
    : "";

  return (
    <div className="map-root" data-hidden={hidden ? "true" : "false"}>
      <div ref={container} className="map-canvas" />
      {tip ? (
        <div className="map-tip" style={{ left: tip.x, top: tip.y }} role="status">
          <strong>{tip.name}</strong>
          {tip.outside || overlays.hex ? <span>{tipValue}</span> : null}
          {overlays.hex && !tip.outside ? <em>{translate(lang, "nandaMap.syntheticFixture")}</em> : null}
        </div>
      ) : null}
      <details className="attrib">
        <summary>{shortCredit}</summary>
        <p>{credit}</p>
      </details>
    </div>
  );
}
