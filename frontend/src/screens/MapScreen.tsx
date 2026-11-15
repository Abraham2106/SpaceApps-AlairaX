import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { cantonAt } from "../lib/geo";
import { compactLine, comparisonSentence, leadSentence, metricNoun, rotationName } from "../lib/plain";
import { ROTATION_ORDER, ROTATION_STYLE } from "../lib/plain";
import { useCantons, useComparison } from "../data/queries";
import { useInstrument } from "../store";

function Thumb({ kind }: { kind: string }) {
  if (kind === "satellite") {
    return (
      <svg className="thumb" viewBox="0 0 44 28" aria-hidden>
        <rect width="44" height="28" fill="#1d4a38" />
        <path d="M4 20c6-8 10-4 16-9s8 2 14-4 6 8 6 8v9H4Z" fill="#c9842a" opacity="0.8" />
        <circle cx="30" cy="8" r="3" fill="#f4efe4" />
      </svg>
    );
  }
  if (kind === "modis") {
    return (
      <svg className="thumb" viewBox="0 0 44 28" aria-hidden>
        <rect width="44" height="28" fill="#16343a" />
        <rect x="6" y="6" width="10" height="10" fill="#6a6e73" />
        <rect x="18" y="8" width="14" height="8" fill="#9a8756" />
      </svg>
    );
  }
  if (kind === "marble") {
    return (
      <svg className="thumb" viewBox="0 0 44 28" aria-hidden>
        <rect width="44" height="28" fill="#0b1c33" />
        <circle cx="22" cy="14" r="9" fill="#1f4d73" />
        <path d="M16 12c3 2 5-2 8-1" stroke="#d6c4a1" fill="none" />
      </svg>
    );
  }
  return (
    <svg className="thumb" viewBox="0 0 44 28" aria-hidden>
      <rect width="44" height="28" fill="#10211c" />
      <path d="M8 22 16 8l8 10 6-6 6 10Z" fill="none" stroke="#f4efe4" />
    </svg>
  );
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
  const toggleCanton = useInstrument((state) => state.toggleCanton);
  const location = useInstrument((state) => state.location);
  const locationMessage = useInstrument((state) => state.locationMessage);
  const setLocation = useInstrument((state) => state.setLocation);
  const [params] = useSearchParams();
  const [query, setQuery] = useState("");
  const [ask, setAsk] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [layersOpen, setLayersOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const cantons = useCantons();
  const comparison = useComparison();
  const loaded = comparison.data;
  const compare = loaded?.compare ?? null;
  const names = Object.fromEntries((loaded?.catalog.rotations ?? []).map((item) => [item.id, item.name]));
  const scenarioName = loaded?.catalog.scenarios.find((item) => item.id === loaded.compare?.scenario_id)?.name
    ?? loaded?.catalog.scenarios.find((item) => item.id === useInstrument.getState().scenarioId)?.name
    ?? "";

  const visible = useMemo(() => {
    const features = cantons.data?.features ?? [];
    const needle = query.trim().toLowerCase();
    const ranked = [...features].sort((a, b) => Number(b.properties.guanacaste) - Number(a.properties.guanacaste) || a.properties.name.localeCompare(b.properties.name, "es"));
    return ranked.filter((feature) => !needle || feature.properties.name.toLowerCase().includes(needle) || feature.properties.sourceName.toLowerCase().includes(needle));
  }, [cantons.data, query]);

  const n = compare?.analog_years.length ?? 0;
  const modelCanton = compare && cantons.data ? cantonAt(compare.zona.longitude, compare.zona.latitude, cantons.data) : null;

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

  async function locate() {
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

  return (
    <>
      <div className="hud left-hud">
        <section className="panel stack" aria-label={spanish ? "Lectura" : "Reading"}>
          <p className="kicker">{scenarioName || (spanish ? "Escenario" : "Scenario")} · n = {n || "…"}</p>
          <h1>{spanish ? "Déficit modelado" : "Modeled deficit"}</h1>
          {comparison.isPending ? <p>{spanish ? "Cargando la comparación…" : "Loading the comparison…"}</p> : null}
          {comparison.isError ? <p className="warn">{spanish ? "No se pudo leer la comparación." : "The comparison could not be read."} {(comparison.error as Error).message}</p> : null}
          {loaded && !compare ? <p className="warn">{loaded.httpDetail}</p> : null}
          {compare ? ROTATION_ORDER.map((id) => {
            const rotation = compare.rotations.find((item) => item.rotation_id === id);
            if (!rotation) return null;
            const sentence = {
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
            };
            return (
              <p key={id} className="prose">
                <span className="swatch" style={{ background: ROTATION_STYLE[id].color, display: "inline-block", marginRight: 8 }} />
                {compactLine(sentence)}
              </p>
            );
          }) : null}
          {compare ? (
            <details>
              <summary>{spanish ? "Leer la frase completa" : "Read the full sentence"}</summary>
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
            </details>
          ) : null}
          <p className="faint">
            {spanish
              ? `Eje: ${metricNoun(metric, lang)}. ${modelCanton ? `El punto del archivo cae en ${modelCanton.properties.name}. ` : ""}Elegir un cantón no cambia estas cifras.`
              : `Axis: ${metricNoun(metric, lang)}. ${modelCanton ? `The file point falls in ${modelCanton.properties.name}. ` : ""}Choosing a canton does not change these numbers.`}
          </p>
          <div className="row">
            <button onClick={() => setAsk(true)}>{spanish ? "Usar mi ubicación" : "Use my location"}</button>
            <button onClick={() => {
              if (!compare || !cantons.data) return;
              const hit = cantonAt(compare.zona.longitude, compare.zona.latitude, cantons.data);
              if (hit) toggleCanton(hit.id, false);
            }}>{spanish ? "Ir al punto del modelo" : "Go to the model point"}</button>
          </div>
          {locationMessage ? <p role="status">{locationMessage}</p> : null}
          {location && !location.inside ? <p className="warn">{spanish ? "Sin extrapolación." : "No extrapolation."}</p> : null}
          <label>
            <span className="kicker">{spanish ? "Buscar cantón" : "Find a canton"}</span>
            <input className="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={spanish ? "Liberia, Nicoya…" : "Liberia, Nicoya…"} />
          </label>
          <div className="canton-list" role="listbox" aria-multiselectable="true" aria-label={spanish ? "Cantones" : "Cantons"}>
            {visible.slice(0, query ? 12 : 11).map((feature) => (
              <button
                key={feature.id}
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
                <span className="faint">{feature.properties.guanacaste ? "Guanacaste" : spanish ? "sin simulación" : "no simulation"}</span>
              </button>
            ))}
          </div>
          <p className="faint">{spanish ? "Mayús y clic suma cantones. La cifra no cambia." : "Shift-click adds cantons. The number does not change."}</p>
          {selected.length === 0 ? <p>{spanish ? "Ningún cantón elegido." : "No canton selected."}</p> : null}
          <div className="row">
            <Link to={{ pathname: "/rotaciones", search: params.toString() }}>{spanish ? "Ver la gráfica" : "See the chart"}</Link>
            <button onClick={() => setShareOpen(true)}>{spanish ? "Compartir" : "Share"}</button>
          </div>
        </section>
      </div>
      <button className="layers-fab only-mobile" onClick={() => setLayersOpen(true)}>{spanish ? "Capas" : "Layers"}</button>
      <div className="hud right-hud hide-mobile" role="toolbar" aria-label={spanish ? "Capas" : "Layers"}>
        {([
          ["satellite", spanish ? "Nítida" : "Sharp"],
          ["modis", "MODIS"],
          ["marble", "Marble"],
        ] as const).map(([id, label]) => (
          <button key={id} className="layer-btn" aria-pressed={basemap === id} onClick={() => setBasemap(id)}>
            <Thumb kind={id} />
            {label}
          </button>
        ))}
        {([
          ["cantons", spanish ? "Cantones" : "Cantons"],
          ["hex", spanish ? "Malla" : "Mesh"],
          ["terrain", spanish ? "Relieve" : "Relief"],
          ["plates", "3D"],
          ["osm", "OSM"],
        ] as const).map(([id, label]) => (
          <button key={id} className="layer-btn" aria-pressed={overlays[id]} onClick={() => toggleOverlay(id)}>
            <Thumb kind={id} />
            {label}
          </button>
        ))}
      </div>
      <div className="hud bottom-hud">
        <div className="panel">
          <div className="row">
            <p className="kicker" style={{ margin: 0 }}>{spanish ? "Abril a diciembre · fechas sin validar" : "April to December · unvalidated dates"}</p>
            <Link to={{ pathname: "/temporada", search: params.toString() }}>{spanish ? "Comparar dos años" : "Compare two years"}</Link>
          </div>
          <div className="timeline">
            {["Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"].map((month) => (
              <div key={month} className="month"><strong>{month}</strong></div>
            ))}
          </div>
        </div>
      </div>
      {overlays.hex ? (
        <p className="attrib" style={{ left: 12, right: "auto", bottom: 210 }}>
          {spanish
            ? "La malla tiene un solo color: el p50 del punto, no un mapa. No hay interpolación."
            : "The mesh has one color: the point’s p50, not a map. There is no interpolation."}
        </p>
      ) : null}
      {layersOpen ? (
        <div className="dialog-back" role="presentation" onClick={() => setLayersOpen(false)}>
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="layers-title" onClick={(event) => event.stopPropagation()}>
            <h2 id="layers-title">{spanish ? "Capas" : "Layers"}</h2>
            <div className="cluster" role="radiogroup" aria-label={spanish ? "Imagen de base" : "Base image"}>
              {([
                ["satellite", spanish ? "Nítida" : "Sharp"],
                ["modis", "MODIS"],
                ["marble", "Marble"],
              ] as const).map(([id, label]) => (
                <button key={id} aria-pressed={basemap === id} onClick={() => setBasemap(id)}>{label}</button>
              ))}
            </div>
            <div className="cluster">
              {([
                ["cantons", spanish ? "Cantones" : "Cantons"],
                ["hex", spanish ? "Malla" : "Mesh"],
                ["terrain", spanish ? "Relieve" : "Relief"],
                ["plates", "3D"],
                ["osm", "OSM"],
              ] as const).map(([id, label]) => (
                <button key={id} aria-pressed={overlays[id]} onClick={() => toggleOverlay(id)}>{label}</button>
              ))}
            </div>
            <p className="faint">{spanish ? "La malla usa un solo color: el valor del punto, no un mapa interpolado." : "The mesh uses one color: the point value, not an interpolated map."}</p>
            <button onClick={() => setLayersOpen(false)}>{spanish ? "Cerrar" : "Close"}</button>
          </div>
        </div>
      ) : null}
      {ask ? (
        <div className="dialog-back" role="presentation" onClick={() => setAsk(false)}>
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="loc-title" onClick={(event) => event.stopPropagation()}>
            <h2 id="loc-title">{spanish ? "Ubicación de este aparato" : "This device’s location"}</h2>
            <p>{spanish ? "El navegador va a pedir permiso. La coordenada solo centra el mapa aquí. No se envía a un servidor y no crea una simulación nueva. Si cae fuera de Guanacaste, se dice y no se extrapola." : "The browser will ask permission. The coordinate only recenters the map here. It is not sent to a server and it does not create a new simulation. Outside Guanacaste, the screen says so and does not extrapolate."}</p>
            <div className="row">
              <button onClick={locate}>{spanish ? "Pedir permiso" : "Ask permission"}</button>
              <button onClick={() => setAsk(false)}>{spanish ? "Ahora no" : "Not now"}</button>
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
              <button onClick={async () => {
                try {
                  await navigator.clipboard.writeText(shareText);
                  setCopied(true);
                } catch {
                  setCopied(false);
                }
              }}>{spanish ? "Copiar" : "Copy"}</button>
              <button onClick={() => setShareOpen(false)}>{spanish ? "Cerrar" : "Close"}</button>
            </div>
            {copied ? <p role="status">{spanish ? "Copiado." : "Copied."}</p> : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
