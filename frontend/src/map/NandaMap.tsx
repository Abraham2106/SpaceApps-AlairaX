import { translate } from "../lib/i18n";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Crosshair, MapPin, Minus, Plus } from "lucide-react";
import maplibregl, { type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { hexMesh } from "../lib/color";
import { boundsOf, cantonAt, guanacasteFeatures } from "../lib/geo";
import { useCantons, useComparison } from "../data/queries";
import { formatValue } from "../lib/format";
import { hexHeight, hexPaint, surfaceValue, useSurface } from "../lib/surface";
import { useInstrument } from "../store";
import type { Lang, MetricId } from "../lib/types";
import { isMobile } from "../lib/viewport";
import { ESRI_TILE_URL, IMAGERY_SOURCES, formatImageryDate, tileUrlFor, type ImagerySourceId } from "./imagery/catalog";
import { selectSource, type ImageryChoice } from "./imagery/selectSource";
import { ImageryBadge } from "./imagery/ImageryBadge";

/** Errores de teselas tolerados antes de dar por caída una fuente con la fecha actual. */
const TILE_ERROR_LIMIT = 3;
const IMAGERY_LAYERS = ["satellite", "modis", "hls", "marble"] as const;

const EMPTY = { type: "FeatureCollection" as const, features: [] };

function buildStyle(imageryDate: string): StyleSpecification {
  const motion = reducedMotion() ? 0 : 680;
  return {
    version: 8,
    glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
    sources: {
      satellite: {
        type: "raster",
        tiles: [ESRI_TILE_URL],
        tileSize: 256,
        maxzoom: 19,
      },
      modis: {
        type: "raster",
        tiles: [tileUrlFor("modis", imageryDate)],
        tileSize: 256,
        maxzoom: IMAGERY_SOURCES.modis.maxzoom,
      },
      // HLS 30 m: solo hay datos el día de una pasada; el resto es transparente y deja ver MODIS.
      hls: {
        type: "raster",
        tiles: [tileUrlFor("hls", imageryDate)],
        tileSize: 256,
        maxzoom: IMAGERY_SOURCES.hls.maxzoom,
      },
      marble: {
        type: "raster",
        tiles: [tileUrlFor("marble", imageryDate)],
        tileSize: 256,
        maxzoom: IMAGERY_SOURCES.marble.maxzoom,
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
          "raster-saturation": 0.06,
          "raster-brightness-max": 1,
          "raster-brightness-min": 0.04,
          "raster-contrast": 0.08,
          "raster-opacity": 1,
        },
      },
      { id: "modis", type: "raster", source: "modis", layout: { visibility: "none" } },
      { id: "hls", type: "raster", source: "hls", layout: { visibility: "none" } },
      { id: "marble", type: "raster", source: "marble", layout: { visibility: "none" } },
      {
        id: "hillshade",
        type: "hillshade",
        source: "dem",
        paint: {
          "hillshade-exaggeration": 0.14,
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
          "fill-color": ["case", ["boolean", ["feature-state", "selected"], false], "#46c47c", "#ffffff"],
          "fill-color-transition": { duration: motion, delay: 0 },
          "fill-opacity-transition": { duration: motion, delay: 0 },
          "fill-opacity": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            0.42,
            ["boolean", ["feature-state", "hover"], false],
            0.16,
            ["get", "guanacaste"],
            0.03,
            0,
          ],
        },
      },
      {
        id: "canton-dots",
        type: "fill",
        source: "cantons",
        paint: {
          "fill-pattern": "dots",
          "fill-opacity-transition": { duration: motion, delay: 0 },
          "fill-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0.85, 0],
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
            ["get", "guanacaste"],
            "rgba(255,255,255,0.82)",
            "rgba(255,255,255,0.3)",
          ],
          "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 2.6, ["boolean", ["feature-state", "hover"], false], 1.8, ["get", "guanacaste"], 1, 0.5],
          "line-opacity": ["case", ["get", "guanacaste"], 1, 0.6],
        },
      },
      {
        id: "canton-label",
        type: "symbol",
        source: "labels",
        layout: {
          "text-field": ["get", "name"],
          "text-font": ["Noto Sans Regular"],
          "text-size": ["interpolate", ["linear"], ["zoom"], 6, 10.5, 10, 13],
          "text-letter-spacing": 0.03,
        },
        paint: {
          "text-color": "#ffffff",
          "text-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0, 1],
          "text-halo-color": "rgba(10,14,12,0.7)",
          "text-halo-width": 1.4,
          "text-halo-blur": 0.8,
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
          "circle-radius": 5.5,
          "circle-color": "#ffffff",
          "circle-stroke-color": "#151714",
          "circle-stroke-width": 2.5,
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
          "text-color": "#ffffff",
          "text-halo-color": "rgba(10,14,12,0.75)",
          "text-halo-width": 1.4,
        },
      },
    ],
  };
}

/** A small white dot tile for the selected-canton pattern. */
function dotTile(): ImageData {
  const size = 12;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d")!;
  context.fillStyle = "rgba(255,255,255,0.95)";
  context.beginPath();
  context.arc(size / 2, size / 2, 1.3, 0, Math.PI * 2);
  context.fill();
  return context.getImageData(0, 0, size, size);
}

function frameGuanacaste(map: maplibregl.Map, collection: Parameters<typeof guanacasteFeatures>[0]) {
  const bounds = boundsOf(guanacasteFeatures(collection));
  if (!bounds) return;
  map.fitBounds([[bounds[0], bounds[1]], [bounds[2], bounds[3]]], {
    padding: framePadding(),
    pitch: 0,
    bearing: 0,
    duration: reducedMotion() ? 0 : 900,
    maxZoom: 8.8,
  });
}

/** Room the floating reading panel takes over the map, so framing keeps the subject visible. */
function framePadding(): maplibregl.PaddingOptions {
  if (isMobile()) return { top: 60, bottom: 24, left: 16, right: 16 };
  const panel = document.querySelector(".map-note")?.getBoundingClientRect();
  return { top: 72, bottom: 56, left: (panel?.right ?? 0) + 32, right: 88 };
}

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function NandaMap({ hidden, inset }: { hidden: boolean; inset: "panel" | "open" }) {
  const container = useRef<HTMLDivElement>(null);
  const attribBar = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const ready = useRef(false);
  const hovered = useRef<string | null>(null);
  const platesWere = useRef(false);
  const surfaceRef = useRef<ReturnType<typeof useSurface>["data"]>(undefined);
  const metricRef = useRef<MetricId>("modeled_water_deficit_mm");
  const tileErrors = useRef<Record<string, number>>({});
  const [zoom, setZoom] = useState(8.05);
  const [failed, setFailed] = useState<ReadonlySet<ImagerySourceId>>(() => new Set());
  const [tip, setTip] = useState<{ x: number; y: number; name: string; value: number | null; outside: boolean } | null>(null);
  const cantons = useCantons();
  const comparison = useComparison();
  const surface = useSurface();
  const basemap = useInstrument((state) => state.basemap);
  const imageryDate = useInstrument((state) => state.imageryDate);
  const overlays = useInstrument((state) => state.overlays);
  const selected = useInstrument((state) => state.selected);
  const selectedCenter = useInstrument((state) => state.selectedCenter);
  const metric = useInstrument((state) => state.metric);
  const lang = useInstrument((state) => state.lang);
  const location = useInstrument((state) => state.location);
  const toggleCanton = useInstrument((state) => state.toggleCanton);
  const toggleOverlay = useInstrument((state) => state.toggleOverlay);
  const setLocation = useInstrument((state) => state.setLocation);
  const [flagElement] = useState(() => document.createElement("div"));
  const flagMarker = useRef<maplibregl.Marker | null>(null);
  useEffect(() => {
    surfaceRef.current = surface.data;
    metricRef.current = metric;
  }, [surface.data, metric]);

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: buildStyle(useInstrument.getState().imageryDate),
      center: [-85.45, 10.45],
      zoom: 8.05,
      pitch: 0,
      bearing: 0,
      maxPitch: 52,
      attributionControl: false,
      fadeDuration: reducedMotion() ? 0 : 280,
    });
    mapRef.current = map;
    map.on("styleimagemissing", (event) => {
      if (event.id === "dots" && !map.hasImage("dots")) map.addImage("dots", dotTile(), { pixelRatio: 2 });
    });
    map.on("load", () => {
      ready.current = true;
      map.setTerrain(null);
    });
    map.on("zoomend", () => setZoom(map.getZoom()));
    // Una fuente que no carga no se oculta en silencio: la ficha de procedencia lo dice.
    map.on("error", (event) => {
      const sourceId = (event as { sourceId?: string }).sourceId;
      if (sourceId !== "modis" && sourceId !== "hls") return;
      const count = (tileErrors.current[sourceId] ?? 0) + 1;
      tileErrors.current[sourceId] = count;
      if (count === TILE_ERROR_LIMIT) setFailed((current) => new Set([...current, sourceId]));
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
            id: feature.id,
            properties: { name: feature.properties.name },
            geometry: { type: "Point" as const, coordinates: feature.properties.center },
          })),
      });
      (map.getSource("hexCoarse") as maplibregl.GeoJSONSource | undefined)?.setData(hexMesh(collection, 0.22, "coarse"));
      (map.getSource("hexMid") as maplibregl.GeoJSONSource | undefined)?.setData(hexMesh(collection, 0.12, "mid"));
      (map.getSource("hexFine") as maplibregl.GeoJSONSource | undefined)?.setData(hexMesh(collection, 0.065, "fine"));
      if (useInstrument.getState().selected.length === 0 && inset === "panel") frameGuanacaste(map, collection);
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [cantons.data, inset]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      map.setLayoutProperty("canton-fill", "visibility", overlays.cantons && !overlays.plates ? "visible" : "none");
      map.setLayoutProperty("canton-dots", "visibility", overlays.cantons && !overlays.plates ? "visible" : "none");
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
  }, [overlays, metric, surface.data]);

  const choice: ImageryChoice = selectSource({ basemap, zoom, date: imageryDate, failed });
  const visibleImagery = choice.layers.map((id) => IMAGERY_SOURCES[id].mapId).join(",");

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const shown = visibleImagery.split(",");
    const apply = () => {
      for (const id of IMAGERY_LAYERS) map.setLayoutProperty(id, "visibility", shown.includes(id) ? "visible" : "none");
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
    return () => { map.off("load", apply); };
  }, [visibleImagery]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    tileErrors.current = {};
    setFailed((current) => (current.size ? new Set() : current));
    const apply = () => {
      (map.getSource("modis") as maplibregl.RasterTileSource | undefined)?.setTiles([tileUrlFor("modis", imageryDate)]);
      (map.getSource("hls") as maplibregl.RasterTileSource | undefined)?.setTiles([tileUrlFor("hls", imageryDate)]);
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
    return () => { map.off("load", apply); };
  }, [imageryDate]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const syncSelection = () => {
      for (const feature of cantons.data?.features ?? []) {
        const state = { selected: selected.includes(feature.id) };
        map.setFeatureState({ source: "cantons", id: feature.id }, state);
        if (feature.properties.guanacaste) map.setFeatureState({ source: "labels", id: feature.id }, state);
      }
      const feature = selected.length === 1 ? cantons.data?.features.find((item) => item.id === selected[0]) : undefined;
      if (!feature) {
        flagMarker.current?.remove();
        return;
      }
      flagMarker.current ??= new maplibregl.Marker({ element: flagElement, anchor: "bottom", offset: [0, -6] });
      flagMarker.current.setLngLat(feature.properties.center).addTo(map);
      map.flyTo({
        center: selectedCenter ?? feature.properties.center,
        zoom: 9.6,
        pitch: 26,
        bearing: -14,
        duration: reducedMotion() ? 0 : 1700,
        curve: 1.35,
        essential: true,
        padding: framePadding(),
      });
    };
    if (ready.current) syncSelection();
    else map.once("load", syncSelection);
    return () => { map.off("load", syncSelection); };
  }, [selected, selectedCenter, cantons.data, flagElement]);

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
    imagery: imageryCredit(choice, lang),
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

  // La ficha y la nota de HLS pueden ocupar dos líneas: el reproductor sube lo mismo.
  useEffect(() => {
    const bar = attribBar.current;
    if (!bar || typeof ResizeObserver === "undefined") return;
    const root = document.documentElement;
    const observer = new ResizeObserver(() => {
      root.style.setProperty("--attrib-h", `${Math.ceil(bar.getBoundingClientRect().height)}px`);
    });
    observer.observe(bar);
    return () => {
      observer.disconnect();
      root.style.removeProperty("--attrib-h");
    };
  }, []);

  const es = lang === "es";
  const flagFeature = selected.length === 1 ? cantons.data?.features.find((item) => item.id === selected[0]) : undefined;
  const flagHoldsPoint = Boolean(flagFeature && pointName === flagFeature.properties.name);

  return (
    <div className="map-root" data-hidden={hidden ? "true" : "false"}>
      <div ref={container} className="map-canvas" />
      {flagFeature ? createPortal(
        <div className="canton-flag">
          <MapPin size={15} strokeWidth={2} aria-hidden />
          <span>
            <strong>{flagFeature.properties.name}</strong>
            <em>{flagHoldsPoint ? (es ? "Punto de simulación" : "Simulation point") : (es ? "Lectura regional" : "Regional reading")}</em>
          </span>
        </div>,
        flagElement,
      ) : null}
      {tip ? (
        <div className="map-tip" style={{ left: tip.x, top: tip.y }} role="status">
          <strong>{tip.name}</strong>
          {tip.outside || overlays.hex ? <span>{tipValue}</span> : null}
          {overlays.hex && !tip.outside ? <em>{translate(lang, "nandaMap.syntheticFixture")}</em> : null}
        </div>
      ) : null}
      {!hidden ? (
        <div className="map-controls" role="group" aria-label={es ? "Controles del mapa" : "Map controls"}>
          <button type="button" aria-label={es ? "Acercar" : "Zoom in"} title={es ? "Acercar" : "Zoom in"} onClick={() => mapRef.current?.zoomIn()}><Plus size={16} strokeWidth={1.8} aria-hidden /></button>
          <button type="button" aria-label={es ? "Alejar" : "Zoom out"} title={es ? "Alejar" : "Zoom out"} onClick={() => mapRef.current?.zoomOut()}><Minus size={16} strokeWidth={1.8} aria-hidden /></button>
          <button type="button" aria-label={es ? "Encuadrar Guanacaste" : "Frame Guanacaste"} title={es ? "Encuadrar Guanacaste" : "Frame Guanacaste"}
            onClick={() => { if (mapRef.current && cantons.data) frameGuanacaste(mapRef.current, cantons.data); }}><Crosshair size={16} strokeWidth={1.8} aria-hidden /></button>
          <button type="button" className="map-control-3d" aria-pressed={overlays.plates} aria-label={es ? "Vista en relieve" : "Raised view"} title={es ? "Vista en relieve" : "Raised view"}
            onClick={() => toggleOverlay("plates")}>{overlays.plates ? "3D" : "2D"}</button>
        </div>
      ) : null}
      <div ref={attribBar} className="attrib-bar">
        <ImageryBadge choice={choice} />
        <details className="attrib">
          <summary>{shortCredit}</summary>
          <p>{credit}</p>
        </details>
      </div>
    </div>
  );
}

function imageryCredit(choice: ImageryChoice, lang: Lang): string {
  const date = choice.date ? formatImageryDate(choice.date, lang) : "";
  const parts = choice.layers.map((id) => {
    if (id === "esri") return translate(lang, choice.fallback ? "nandaMap.satelliteFallbackCredit" : "nandaMap.satelliteCredit");
    if (id === "marble") return translate(lang, "nandaMap.marbleCredit");
    return translate(lang, id === "hls" ? "nandaMap.hlsCredit" : "nandaMap.modisCredit", { date });
  });
  return parts.join("; ");
}
