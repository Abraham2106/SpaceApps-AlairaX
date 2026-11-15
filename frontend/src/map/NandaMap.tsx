import { useEffect, useMemo, useRef } from "react";
import maplibregl, { type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { hexMesh, metricColor } from "../lib/color";
import { boundsOf, cantonAt, guanacasteFeatures } from "../lib/geo";
import { useCantons, useComparison } from "../data/queries";
import { useInstrument } from "../store";

const EMPTY = { type: "FeatureCollection" as const, features: [] };

function buildStyle(): StyleSpecification {
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
      { id: "satellite", type: "raster", source: "satellite" },
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
          "fill-color": "#d7e6f0",
          "fill-opacity": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            0.16,
            ["boolean", ["feature-state", "hover"], false],
            0.08,
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
            paint: { "fill-color": "#9a8756", "fill-opacity": 0.45 },
          },
          {
            id: `hex-${res}-extrude`,
            type: "fill-extrusion" as const,
            source,
            layout: { visibility: "none" as const },
            paint: {
              "fill-extrusion-color": "#9a8756",
              "fill-extrusion-height": 500,
              "fill-extrusion-opacity": 0.55,
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
          "line-color": ["case", ["boolean", ["feature-state", "selected"], false], "#d7f1ff", ["get", "guanacaste"], "rgba(232,242,248,0.92)", "rgba(232,242,248,0.28)"],
          "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 1.6, ["get", "guanacaste"], 1.05, 0.4],
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
          "text-color": "#e7eef4",
          "text-halo-color": "#0c1014",
          "text-halo-width": 1.1,
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
          "text-size": 11,
          "text-offset": [0, 1.1],
          "text-anchor": "top",
        },
        paint: {
          "text-color": "#fff6e0",
          "text-halo-color": "#1a1208",
          "text-halo-width": 1.5,
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
  const cantons = useCantons();
  const comparison = useComparison();
  const basemap = useInstrument((state) => state.basemap);
  const overlays = useInstrument((state) => state.overlays);
  const selected = useInstrument((state) => state.selected);
  const metric = useInstrument((state) => state.metric);
  const lang = useInstrument((state) => state.lang);
  const location = useInstrument((state) => state.location);
  const toggleCanton = useInstrument((state) => state.toggleCanton);
  const setLocation = useInstrument((state) => state.setLocation);

  const color = useMemo(() => {
    const compare = comparison.data?.compare;
    const row = compare?.rotations.find((item) => item.rotation_id === "rice_melon");
    return metricColor(metric, row?.metrics[metric].p50 ?? null);
  }, [comparison.data, metric]);

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: buildStyle(),
      center: [-85.45, 10.45],
      zoom: 8.05,
      pitch: 0,
      bearing: 0,
      maxPitch: 0,
      attributionControl: false,
      fadeDuration: reducedMotion() ? 0 : 280,
    });
    mapRef.current = map;
    map.on("load", () => {
      ready.current = true;
      map.setTerrain(null);
      const canvas = map.getCanvas();
      canvas.setAttribute("role", "application");
      const spanish = useInstrument.getState().lang === "es";
      canvas.setAttribute(
        "aria-label",
        spanish
          ? "Mapa de Costa Rica. Las flechas lo mueven. Los cantones también están en la lista."
          : "Map of Costa Rica. Arrow keys pan. Cantons are also in the list.",
      );
    });
    map.on("click", "canton-fill", (event) => {
      const feature = event.features?.[0];
      if (!feature) return;
      const guanacaste = Boolean(feature.properties.guanacaste);
      const id = String(feature.id ?? feature.properties.id);
      if (!guanacaste) {
        const spanish = useInstrument.getState().lang === "es";
        setLocation(useInstrument.getState().location, spanish
          ? `${feature.properties.name}: sin simulación disponible. El modelo no sale de Guanacaste y no se extrapola.`
          : `${feature.properties.name}: no simulation available. The model stays in Guanacaste and is not extrapolated.`);
        return;
      }
      toggleCanton(id, event.originalEvent.shiftKey);
    });
    map.on("mousemove", "canton-fill", (event) => {
      map.getCanvas().style.cursor = "pointer";
      const id = event.features?.[0]?.id;
      if (id == null) return;
      const next = String(id);
      if (hovered.current && hovered.current !== next) {
        map.setFeatureState({ source: "cantons", id: hovered.current }, { hover: false });
      }
      hovered.current = next;
      map.setFeatureState({ source: "cantons", id: next }, { hover: true });
    });
    map.on("mouseleave", "canton-fill", () => {
      map.getCanvas().style.cursor = "";
      if (hovered.current) map.setFeatureState({ source: "cantons", id: hovered.current }, { hover: false });
      hovered.current = null;
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
          const narrow = window.innerWidth < 800;
          map.fitBounds(
            [[bounds[0], bounds[1]], [bounds[2], bounds[3]]],
            {
              padding: narrow
                ? { top: 36, bottom: 150, left: 10, right: 10 }
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
      map.setLayoutProperty("hillshade", "visibility", overlays.terrain ? "visible" : "none");
      map.setTerrain(null);
      const zoom = map.getZoom();
      const level = zoom < 8.2 ? "coarse" : zoom < 10 ? "mid" : "fine";
      for (const res of ["coarse", "mid", "fine"]) {
        const show = overlays.hex && res === level;
        map.setLayoutProperty(`hex-${res}`, "visibility", show && !overlays.plates ? "visible" : "none");
        map.setLayoutProperty(`hex-${res}-extrude`, "visibility", show && overlays.plates ? "visible" : "none");
        map.setPaintProperty(`hex-${res}`, "fill-color", color);
        map.setPaintProperty(`hex-${res}-extrude`, "fill-extrusion-color", color);
      }
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
    map.on("zoomend", apply);
    return () => {
      map.off("zoomend", apply);
    };
  }, [basemap, overlays, color]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    for (const feature of cantons.data?.features ?? []) {
      map.setFeatureState({ source: "cantons", id: feature.id }, { selected: selected.includes(feature.id) });
    }
    if (selected.length !== 1) return;
    const feature = cantons.data?.features.find((item) => item.id === selected[0]);
    if (!feature) return;
    const narrow = window.innerWidth < 800;
    map.flyTo({
      center: feature.properties.center,
      zoom: 9.6,
      pitch: 0,
      bearing: 0,
      duration: reducedMotion() ? 0 : 1700,
      curve: 1.35,
      essential: true,
      padding: narrow ? { top: 30, bottom: 200, left: 16, right: 72 } : { left: 430, right: 96, top: 24, bottom: 80 },
    });
  }, [selected, cantons.data]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const zona = comparison.data?.compare?.zona ?? comparison.data?.catalog.zona;
    const features: { type: "Feature"; properties: { kind: string; label?: string }; geometry: { type: "Point"; coordinates: [number, number] } }[] = [];
    if (zona) {
      features.push({
        type: "Feature" as const,
        properties: { kind: "model", label: `${zona.latitude.toFixed(2)}, ${zona.longitude.toFixed(2)}` },
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
  }, [comparison.data, location]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !location) return;
    map.flyTo({
      center: [location.longitude, location.latitude],
      zoom: Math.max(map.getZoom(), 10),
      pitch: 0,
      bearing: 0,
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
  const credit =
    lang === "es"
      ? `Imagen: ${basemap === "satellite" ? "Esri, Maxar, Earthstar Geographics (no es NASA)" : basemap === "modis" ? "NASA GIBS, MODIS Terra, 12 mar 2024" : "NASA GIBS, Blue Marble"}. Relieve: teselas AWS terrarium (GMTED2010, ETOPO1; no entra al modelo). Límites: geoBoundaries CRI ADM2, CC0, 2020.${overlays.osm ? " Calles y nombres: © OpenFreeMap © colaboradores de OpenStreetMap." : ""} Punto del modelo${pointName ? ` dentro de ${pointName}` : ""}: ${zona ? `${zona.latitude.toFixed(2)}, ${zona.longitude.toFixed(2)}` : "…"}.`
      : `Imagery: ${basemap === "satellite" ? "Esri, Maxar, Earthstar Geographics (not NASA)" : basemap === "modis" ? "NASA GIBS, MODIS Terra, 12 Mar 2024" : "NASA GIBS, Blue Marble"}. Relief: AWS terrarium tiles (GMTED2010, ETOPO1; not a model input). Boundaries: geoBoundaries CRI ADM2, CC0, 2020.${overlays.osm ? " Roads and names: © OpenFreeMap © OpenStreetMap contributors." : ""} Model point${pointName ? ` inside ${pointName}` : ""}: ${zona ? `${zona.latitude.toFixed(2)}, ${zona.longitude.toFixed(2)}` : "…"}.`;

  return (
    <div className="map-root" data-hidden={hidden ? "true" : "false"}>
      <div ref={container} className="map-canvas" />
      <p className="attrib">{credit}</p>
    </div>
  );
}
