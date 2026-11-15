import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Box, Globe2, Hexagon, Layers, LocateFixed, Mountain, Pause, Pentagon, Play, Route, Satellite, ScanLine, Search, Share2 } from "lucide-react";
import { formatNumber, formatSigned, formatValue, metricUnit } from "../lib/format";
import { cantonAt } from "../lib/geo";
import { ROTATION_ORDER, ROTATION_STYLE, comparisonSentence, leadSentence, metricNoun, rotationName } from "../lib/plain";
import { surfaceColor, surfaceDomain, surfaceValue, useSurface } from "../lib/surface";
import { useCantons, useComparison } from "../data/queries";
import { useInstrument } from "../store";
import type { RotationId } from "../lib/types";

const SEASON_DAYS = 274;
const STAGES = [
  { day: 0, es: "Ventana", en: "Window" },
  { day: 44, es: "Arroz 15 may", en: "Rice 15 May" },
  { day: 197, es: "Caupí / sorgo", en: "Cowpea / sorghum" },
  { day: 244, es: "Melón 1 dic", en: "Melon 1 Dec" },
];
const MONTHS = [
  [0, "Abr", "Apr"],
  [30, "May", "May"],
  [61, "Jun", "Jun"],
  [91, "Jul", "Jul"],
  [122, "Ago", "Aug"],
  [153, "Sep", "Sep"],
  [183, "Oct", "Oct"],
  [214, "Nov", "Nov"],
  [244, "Dic", "Dec"],
] as const;

const ICONS = {
  satellite: Satellite,
  modis: ScanLine,
  marble: Globe2,
  cantons: Pentagon,
  hex: Hexagon,
  terrain: Mountain,
  plates: Box,
  osm: Route,
} as const;

function stageAt(day: number, spanish: boolean) {
  const hit = [...STAGES].reverse().find((stage) => day >= stage.day) ?? STAGES[0];
  return spanish ? hit.es : hit.en;
}

export function MapScreen() {
  const lang = useInstrument((state) => state.lang);
  const spanish = lang === "es";
  const metric = useInstrument((state) => state.metric);
  const basemap = useInstrument((state) => state.basemap);
  const setBasemap = useInstrument((state) => state.setBasemap);
  const overlays = useInstrument((state) => state.overlays);
  const toggleOverlay = useInstrument((state) => state.toggleOverlay);
  const selected = useInstrument((state) => state.selected);
  const hovered = useInstrument((state) => state.hovered);
  const toggleCanton = useInstrument((state) => state.toggleCanton);
  const location = useInstrument((state) => state.location);
  const locationMessage = useInstrument((state) => state.locationMessage);
  const setLocation = useInstrument((state) => state.setLocation);
  const yearA = useInstrument((state) => state.yearA);
  const yearB = useInstrument((state) => state.yearB);
  const setYears = useInstrument((state) => state.setYears);
  const [params] = useSearchParams();
  const [query, setQuery] = useState("");
  const [ask, setAsk] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [layersOpen, setLayersOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [open, setOpen] = useState(true);
  const [day, setDay] = useState(44);
  const [playing, setPlaying] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const sheetRef = useRef<HTMLElement>(null);
  const cantons = useCantons();
  const comparison = useComparison();
  const surface = useSurface();
  const loaded = comparison.data;
  const compare = loaded?.compare ?? null;
  const names = Object.fromEntries((loaded?.catalog.rotations ?? []).map((item) => [item.id, item.name]));
  const scenarioName = loaded?.catalog.scenarios.find((item) => item.id === loaded.compare?.scenario_id)?.name
    ?? loaded?.catalog.scenarios.find((item) => item.id === useInstrument.getState().scenarioId)?.name
    ?? "";
  const [min, max] = surfaceDomain(surface.data, metric);

  const visible = useMemo(() => {
    const features = cantons.data?.features ?? [];
    const needle = query.trim().toLowerCase();
    const ranked = [...features].sort((a, b) => Number(b.properties.guanacaste) - Number(a.properties.guanacaste) || a.properties.name.localeCompare(b.properties.name, "es"));
    return ranked.filter((feature) => !needle || feature.properties.name.toLowerCase().includes(needle) || feature.properties.sourceName.toLowerCase().includes(needle));
  }, [cantons.data, query]);

  const n = compare?.analog_years.length ?? 0;
  const modelCanton = compare && cantons.data ? cantonAt(compare.zona.longitude, compare.zona.latitude, cantons.data) : null;
  const focusId = hovered ?? selected[0] ?? null;
  const focus = focusId ? cantons.data?.features.find((feature) => feature.id === focusId) ?? null : null;
  const outside = Boolean(focus && !focus.properties.guanacaste);
  const synthetic = focus?.properties.guanacaste ? surfaceValue(surface.data, focus.id, metric) : null;
  const version = compare?.rotations[0]?.runs[0]?.model_version ?? "";

  function reading(id: RotationId): { value: number | null; delta: number | null } {
    if (outside) return { value: null, delta: null };
    if (synthetic) {
      if (id === "rice_melon") return { value: synthetic.rice_melon, delta: null };
      if (id === "rice_legume") return { value: synthetic.rice_legume, delta: synthetic.delta_legume };
      return { value: synthetic.rice_sorghum, delta: synthetic.delta_sorghum };
    }
    const rotation = compare?.rotations.find((item) => item.rotation_id === id);
    return {
      value: rotation?.metrics[metric].p50 ?? null,
      delta: id === compare?.baseline_rotation_id ? null : rotation?.delta_vs_baseline[metric].p50 ?? null,
    };
  }

  const lead = reading("rice_melon");
  const barMax = Math.max(
    1,
    ...ROTATION_ORDER.map((id) => reading(id).value ?? 0),
  );

  const shareText = compare
    ? [
        leadSentence(lang, scenarioName, metric, n, compare._mock),
        ...ROTATION_ORDER.map((id) => {
          const rotation = compare.rotations.find((item) => item.rotation_id === id);
          if (!rotation) return "";
          return comparisonSentence({
            lang,
            scenarioName,
            metric,
            rotationName: rotationName(id, lang, names[id]),
            baselineName: rotationName(compare.baseline_rotation_id, lang, names[compare.baseline_rotation_id]),
            isBaseline: id === compare.baseline_rotation_id,
            p50: rotation.metrics[metric].p50,
            deltaP50: rotation.delta_vs_baseline[metric].p50,
            n: rotation.metrics[metric].n,
            like2026: compare.scenario_id === "like_2026",
          });
        }),
        window.location.href,
      ].filter(Boolean).join("\n\n")
    : spanish ? "Todavía no hay una comparación para compartir." : "There is no comparison to share yet.";

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setDay((current) => {
        if (current >= SEASON_DAYS) {
          setPlaying(false);
          return SEASON_DAYS;
        }
        return Math.min(SEASON_DAYS, current + 4);
      });
    }, 160);
    return () => window.clearInterval(timer);
  }, [playing]);

  function locate() {
    setAsk(false);
    if (!navigator.geolocation) {
      setLocation(null, spanish ? "Este navegador no entrega la ubicación." : "This browser does not provide a location.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const hit = cantons.data ? cantonAt(position.coords.longitude, position.coords.latitude, cantons.data) : null;
        const inside = Boolean(hit?.properties.guanacaste);
        setLocation(
          {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            inside,
            cantonId: hit?.id ?? null,
            cantonName: hit?.properties.name ?? null,
          },
          inside
            ? spanish
              ? `Ubicación en ${hit?.properties.name ?? "Guanacaste"}. Sirve para centrar el mapa en este aparato. Las cifras siguen siendo del punto provisional, no de este GPS.`
              : `Location in ${hit?.properties.name ?? "Guanacaste"}. It only recenters the map on this device. The numbers remain the provisional point, not this GPS fix.`
            : spanish
              ? "Este punto está fuera de Guanacaste. El modelo no está calibrado aquí y no se extrapola."
              : "This point is outside Guanacaste. The model is not calibrated here and is not extrapolated.",
        );
      },
      () => setLocation(null, spanish ? "No se concedió la ubicación. Podés elegir un cantón en la lista." : "Location was denied. You can pick a canton from the list."),
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 },
    );
  }

  function onHandleDown(event: ReactPointerEvent) {
    if (window.innerWidth >= 800) return;
    const startY = event.clientY;
    const start = sheetRef.current?.getBoundingClientRect().height ?? 280;
    const move = (pointer: PointerEvent) => {
      const next = Math.min(window.innerHeight * 0.74, Math.max(168, start + (startY - pointer.clientY)));
      document.documentElement.style.setProperty("--sheet", `${next}px`);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  const layerButtons = (
    <>
      {([
        ["satellite", spanish ? "Foto" : "Photo"],
        ["modis", spanish ? "NASA" : "NASA"],
        ["marble", spanish ? "Mármol" : "Marble"],
      ] as const).map(([id, label]) => {
        const Icon = ICONS[id];
        return (
          <button key={id} className="layer-btn" aria-pressed={basemap === id} onClick={() => setBasemap(id)}>
            <Icon size={22} strokeWidth={1.5} aria-hidden />
            {label}
          </button>
        );
      })}
      {([
        ["cantons", spanish ? "Cantones" : "Cantons"],
        ["hex", spanish ? "Malla" : "Mesh"],
        ["terrain", spanish ? "Relieve" : "Relief"],
        ["plates", spanish ? "Altura" : "Height"],
        ["osm", spanish ? "Calles" : "Roads"],
      ] as const).map(([id, label]) => {
        const Icon = ICONS[id];
        return (
          <button key={id} className="layer-btn" aria-pressed={overlays[id]} onClick={() => toggleOverlay(id)}>
            <Icon size={22} strokeWidth={1.5} aria-hidden />
            {label}
          </button>
        );
      })}
    </>
  );

  return (
    <>
      <form className="map-search" role="search" onSubmit={(event) => event.preventDefault()}>
        <Search size={16} strokeWidth={1.5} aria-hidden />
        <input className="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={spanish ? "Buscar cantón" : "Find a canton"} aria-label={spanish ? "Buscar cantón" : "Find a canton"} />
      </form>
      <aside ref={sheetRef} className={`left-hud ${open ? "" : "is-collapsed"} ${hovered ? "is-linked" : ""}`}>
        <section className="glass stack" aria-label={spanish ? "Lectura" : "Reading"}>
          <button className="sheet-handle" type="button" aria-label={spanish ? "Arrastrar la ficha" : "Drag the card"} onPointerDown={onHandleDown} />
          <div className="glass-top">
            <button type="button" className="text-btn" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
              {open ? (spanish ? "Ocultar" : "Hide") : (spanish ? "Lectura" : "Reading")}
            </button>
          </div>
          {open ? (
            <>
              <p className="readout">
                {lead.value == null ? (spanish ? "sin dato" : "no data") : formatNumber(lead.value, lang, lead.value % 1 === 0 ? 0 : 1)}
                {lead.value == null ? null : <small>{metricUnit(metric, lang)}</small>}
              </p>
              <h1>{metricNoun(metric, lang)}</h1>
              <p className="faint">{scenarioName} · n = {n || "…"}</p>
              <p className="kicker">
                {outside && focus
                  ? `${focus.properties.name} · ${spanish ? "sin simulación" : "no simulation"}`
                  : synthetic && focus
                    ? `${focus.properties.name} · ${spanish ? "fixture sintético" : "synthetic fixture"}`
                    : spanish ? "punto del modelo" : "model point"}
              </p>
              {comparison.isPending ? <p className="kicker">{spanish ? "Cargando…" : "Loading…"}</p> : null}
              {comparison.isError ? <p className="warn">{spanish ? "No se pudo leer la comparación." : "The comparison could not be read."}</p> : null}
              {outside ? null : (
                <div className="bullets">
                  {ROTATION_ORDER.map((id) => {
                    const item = reading(id);
                    const width = item.value == null ? 0 : Math.min(100, (item.value / barMax) * 100);
                    const color = ROTATION_STYLE[id].color;
                    return (
                      <div key={id} className="bullet">
                        <div className="bullet-top">
                          <span><i style={{ background: color }} />{rotationName(id, lang, names[id])}</span>
                          <strong>{item.value == null ? (spanish ? "sin dato" : "no data") : formatValue(item.value, metric, lang)}</strong>
                        </div>
                        <div className="bullet-track" aria-hidden>
                          {item.value == null ? null : <span className="bullet-bar" style={{ width: `${width}%`, background: `color-mix(in srgb, ${color} 58%, white)` }} />}
                          {id !== "rice_melon" && lead.value != null ? <span className="bullet-mark" style={{ left: `${(lead.value / barMax) * 100}%` }} /> : null}
                        </div>
                        <span className="bullet-delta">
                          {item.delta == null
                            ? (spanish ? "referencia" : "reference")
                            : `${formatSigned(item.delta, metric, lang)} ${spanish ? "vs arroz→melón" : "vs rice→melon"}`}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
              {compare ? <p className="meta-line">{version} · {compare.warnings.length} {spanish ? "avisos" : "warnings"}</p> : null}
              {compare ? (
                <details>
                  <summary>{spanish ? "Leer más" : "Read more"}</summary>
                  <p>{leadSentence(lang, scenarioName, metric, n, compare._mock)}</p>
                  {ROTATION_ORDER.map((id) => {
                    const rotation = compare.rotations.find((item) => item.rotation_id === id);
                    if (!rotation) return null;
                    return (
                      <p key={id}>
                        {comparisonSentence({
                          lang,
                          scenarioName,
                          metric,
                          rotationName: rotationName(id, lang, names[id]),
                          baselineName: rotationName(compare.baseline_rotation_id, lang, names[compare.baseline_rotation_id]),
                          isBaseline: id === compare.baseline_rotation_id,
                          p50: rotation.metrics[metric].p50,
                          deltaP50: rotation.delta_vs_baseline[metric].p50,
                          n: rotation.metrics[metric].n,
                          like2026: compare.scenario_id === "like_2026",
                        })}
                      </p>
                    );
                  })}
                  <p>{compare.warnings.join(" ")}</p>
                  <p className="faint">
                    {spanish
                      ? `Eje: ${metricNoun(metric, lang)}. ${modelCanton ? `El punto del archivo cae en ${modelCanton.properties.name}. ` : ""}Elegir un cantón no cambia la lectura del punto.`
                      : `Axis: ${metricNoun(metric, lang)}. ${modelCanton ? `The file point falls in ${modelCanton.properties.name}. ` : ""}Choosing a canton does not change the point reading.`}
                  </p>
                </details>
              ) : null}
              <div className="row">
                <button type="button" onClick={() => setAsk(true)}><LocateFixed size={16} strokeWidth={1.5} aria-hidden /> {spanish ? "Usar mi ubicación" : "Use my location"}</button>
                <button type="button" onClick={() => {
                  if (!compare || !cantons.data) return;
                  const hit = cantonAt(compare.zona.longitude, compare.zona.latitude, cantons.data);
                  if (hit) toggleCanton(hit.id, false);
                }}>{spanish ? "Ir al punto del modelo" : "Go to the model point"}</button>
              </div>
              {locationMessage ? <p className="kicker" role="status">{locationMessage}</p> : null}
              {location && !location.inside ? <p className="warn">{spanish ? "Sin extrapolación." : "No extrapolation."}</p> : null}
              <div className="canton-list" role="listbox" aria-multiselectable="true" aria-label={spanish ? "Cantones" : "Cantons"}>
                {visible.slice(0, query ? 12 : 11).map((feature) => (
                  <button
                    key={feature.id}
                    type="button"
                    role="option"
                    aria-selected={selected.includes(feature.id)}
                    onClick={(event) => {
                      if (!feature.properties.guanacaste) {
                        setLocation(location, spanish ? `${feature.properties.name}: sin simulación disponible.` : `${feature.properties.name}: no simulation available.`);
                        return;
                      }
                      toggleCanton(feature.id, event.shiftKey);
                    }}
                  >
                    <span>{feature.properties.name}</span>
                    <span className="faint">{feature.properties.guanacaste ? "" : spanish ? "sin simulación" : "no simulation"}</span>
                  </button>
                ))}
              </div>
              <div className="row">
                <Link to={{ pathname: "/rotaciones", search: params.toString() }}>{spanish ? "Ver la gráfica" : "See the chart"}</Link>
                <button type="button" onClick={() => setShareOpen(true)}><Share2 size={16} strokeWidth={1.5} aria-hidden /> {spanish ? "Compartir" : "Share"}</button>
              </div>
            </>
          ) : null}
        </section>
      </aside>
      <button className="layers-fab only-mobile" type="button" onClick={() => setLayersOpen(true)}><Layers size={18} strokeWidth={1.5} aria-hidden /> {spanish ? "Capas" : "Layers"}</button>
      <div className="hud right-hud hide-mobile" role="toolbar" aria-label={spanish ? "Capas" : "Layers"}>
        {layerButtons}
      </div>
      <div className="map-legend" aria-label={spanish ? "Escala" : "Scale"}>
        <div className="legend-top">
          <span>{formatNumber(min, lang, 0)}</span>
          <span>{spanish ? "fixture sintético · arroz→melón" : "synthetic fixture · rice→melon"}</span>
          <span>{formatNumber(max, lang, 0)}</span>
        </div>
        <div className="legend">
          {Array.from({ length: 7 }, (_, index) => (
            <span key={index} style={{ background: surfaceColor(min + ((max - min) * index) / 6, min, max) }} />
          ))}
        </div>
        <p>{spanish ? "Gris: sin simulación. No es la salida del modelo." : "Gray: no simulation. Not a model output."}</p>
      </div>
      <div className="hud bottom-hud">
        <div className="player">
          <button type="button" className="play" aria-pressed={playing} onClick={() => {
            if (day >= SEASON_DAYS) setDay(0);
            setPlaying((value) => !value);
          }}>{playing ? <Pause size={16} strokeWidth={1.5} aria-hidden /> : <Play size={16} strokeWidth={1.5} aria-hidden />} {playing ? (spanish ? "Pausa" : "Pause") : "Play"}</button>
          <div className="scrub">
            <div className="scrub-stages" aria-hidden>
              {STAGES.map((stage) => (
                <i key={stage.day} style={{ left: `${(stage.day / SEASON_DAYS) * 100}%` }} title={spanish ? stage.es : stage.en} />
              ))}
            </div>
            <input
              type="range"
              min={0}
              max={SEASON_DAYS}
              value={day}
              aria-valuetext={stageAt(day, spanish)}
              aria-label={spanish ? "Temporada, abril a diciembre" : "Season, April to December"}
              onChange={(event) => {
                setPlaying(false);
                setDay(Number(event.target.value));
              }}
            />
            <div className="scrub-months" aria-hidden>
              {MONTHS.map(([at, es, en]) => (
                <span key={es} style={{ left: `${(at / SEASON_DAYS) * 100}%` }}>{spanish ? es : en}</span>
              ))}
            </div>
          </div>
          <p className="player-now">{stageAt(day, spanish)}</p>
          <button type="button" aria-expanded={compareOpen} onClick={() => setCompareOpen((value) => !value)}>
            {spanish ? "Comparar años" : "Compare years"}
          </button>
        </div>
        {compareOpen && compare ? (
          <div className="year-pop">
            <label>{spanish ? "Año A" : "Year A"}
              <select value={yearA ?? ""} onChange={(event) => setYears(event.target.value ? Number(event.target.value) : null, yearB)}>
                <option value="">—</option>
                {compare.analog_years.map((item) => <option key={item.year} value={item.year}>{item.year}</option>)}
              </select>
            </label>
            <label>{spanish ? "Año B" : "Year B"}
              <select value={yearB ?? ""} onChange={(event) => setYears(yearA, event.target.value ? Number(event.target.value) : null)}>
                <option value="">—</option>
                {compare.analog_years.map((item) => <option key={item.year} value={item.year}>{item.year}</option>)}
              </select>
            </label>
            <p className="kicker">
              {spanish
                ? "Años análogos del archivo. Este resultado no trae balance diario, así que no se dibuja una curva."
                : "Analog years from the file. This result has no daily balance, so no curve is drawn."}
            </p>
          </div>
        ) : null}
      </div>
      {layersOpen ? (
        <div className="dialog-back" role="presentation" onClick={() => setLayersOpen(false)}>
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="layers-title" onClick={(event) => event.stopPropagation()}>
            <h2 id="layers-title">{spanish ? "Capas" : "Layers"}</h2>
            <div className="layer-grid">{layerButtons}</div>
            <p className="faint">{spanish ? "Cada hexágono copia el valor sintético del cantón que lo contiene. No hay interpolación." : "Each hexagon copies the synthetic value of the canton that contains it. There is no interpolation."}</p>
            <button type="button" onClick={() => setLayersOpen(false)}>{spanish ? "Cerrar" : "Close"}</button>
          </div>
        </div>
      ) : null}
      {ask ? (
        <div className="dialog-back" role="presentation" onClick={() => setAsk(false)}>
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="loc-title" onClick={(event) => event.stopPropagation()}>
            <h2 id="loc-title">{spanish ? "Ubicación de este aparato" : "This device’s location"}</h2>
            <p>{spanish ? "El navegador va a pedir permiso. La coordenada solo centra el mapa aquí. No se envía a un servidor y no crea una simulación nueva. Si cae fuera de Guanacaste, se dice y no se extrapola." : "The browser will ask permission. The coordinate only recenters the map here. It is not sent to a server and it does not create a new simulation. Outside Guanacaste, the screen says so and does not extrapolate."}</p>
            <div className="row">
              <button type="button" onClick={locate}>{spanish ? "Pedir permiso" : "Ask permission"}</button>
              <button type="button" onClick={() => setAsk(false)}>{spanish ? "Ahora no" : "Not now"}</button>
            </div>
          </div>
        </div>
      ) : null}
      {shareOpen ? (
        <div className="dialog-back" role="presentation" onClick={() => setShareOpen(false)}>
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="share-title" onClick={(event) => event.stopPropagation()}>
            <h2 id="share-title">{spanish ? "Compartir esta lectura" : "Share this reading"}</h2>
            <textarea readOnly value={shareText} />
            <div className="row">
              <button type="button" onClick={async () => {
                try {
                  await navigator.clipboard.writeText(shareText);
                  setCopied(true);
                } catch {
                  setCopied(false);
                }
              }}>{spanish ? "Copiar" : "Copy"}</button>
              <button type="button" onClick={() => setShareOpen(false)}>{spanish ? "Cerrar" : "Close"}</button>
            </div>
            {copied ? <p role="status">{spanish ? "Copiado." : "Copied."}</p> : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
