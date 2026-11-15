import { ArrowUpRight } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import plates from "../geo/plates.json";
import { useInstrument } from "../store";
import { useCantons, useComparison } from "../data/queries";
import { cantonAt } from "../lib/geo";
import { formatNumber } from "../lib/format";

const GUANACASTE = [...plates].sort((a, b) => a.name.localeCompare(b.name, "es"));

export function CantonsScreen() {
  const lang = useInstrument((state) => state.lang);
  const spanish = lang === "es";
  const selectOnly = useInstrument((state) => state.selectOnly);
  const selected = useInstrument((state) => state.selected);
  const [params] = useSearchParams();
  const comparison = useComparison();
  const cantons = useCantons();
  const zona = comparison.data?.compare?.zona ?? comparison.data?.catalog.zona;
  const point = zona && cantons.data ? cantonAt(zona.longitude, zona.latitude, cantons.data) : null;
  const plate = GUANACASTE.find(({ id }) => id === selected[0])
    ?? GUANACASTE.find(({ id }) => id === point?.id)
    ?? GUANACASTE[0];
  const mapParams = new URLSearchParams(params);
  mapParams.set("c", plate.id);

  return (
    <div className="screen">
      <article className="detail-page">
        <header className="detail-header">
          <h1>{spanish ? "Cantones de Guanacaste" : "Cantons of Guanacaste"}</h1>
          <p>{spanish ? "Explorá los límites de los 11 cantones. Las cifras corresponden al mismo punto del modelo." : "Explore the boundaries of the 11 cantons. The figures come from the same model point."}</p>
        </header>
        <section className="detail-panel canton-panel" aria-labelledby="canton-name">
          <div className="canton-info">
            <div className="detail-field">
              <label htmlFor="canton-selector">{spanish ? "Elegir cantón" : "Choose a canton"}</label>
              <select id="canton-selector" value={plate.id} onChange={(event) => selectOnly(event.target.value)}>
                {GUANACASTE.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
              </select>
            </div>
            <h2 id="canton-name">{plate.name}</h2>
            {point?.id === plate.id && zona ? (
              <p className="detail-lead">
                {zona.validated
                  ? (spanish ? "El punto del modelo cae dentro de este cantón." : "The model point falls inside this canton.")
                  : (spanish ? "El punto provisional del modelo cae dentro de este cantón." : "The provisional model point falls inside this canton.")}
              </p>
            ) : null}
          </div>
          <figure className="canton-figure">
            <svg viewBox="0 0 100 100" role="img" aria-labelledby="canton-outline-title">
              <title id="canton-outline-title">{spanish ? "Límite de " : "Boundary of "}{plate.name}</title>
              <path d={plate.path} fill={plate.tint} stroke="var(--outline)" strokeWidth="0.6" />
            </svg>
          </figure>
          <div className="canton-details">
            <dl className="canton-meta">
              <div>
                <dt>{spanish ? "Centro de referencia" : "Reference center"}</dt>
                <dd>{formatNumber(plate.center[1], lang, 3)}° / {formatNumber(plate.center[0], lang, 3)}°</dd>
              </div>
              <div>
                <dt>{spanish ? "Límites" : "Boundaries"}</dt>
                <dd>geoBoundaries</dd>
              </div>
              {point?.id === plate.id && zona ? (
                <div>
                  <dt>{spanish ? "Punto del modelo" : "Model point"}</dt>
                  <dd>{formatNumber(zona.latitude, lang, 3)}° / {formatNumber(zona.longitude, lang, 3)}°</dd>
                </div>
              ) : null}
            </dl>
            <Link className="detail-action" to={{ pathname: "/", search: mapParams.toString() }} onClick={() => selectOnly(plate.id)}>
              {spanish ? "Ver cantón en el mapa" : "View canton on the map"} <ArrowUpRight size={16} aria-hidden="true" />
            </Link>
          </div>
        </section>
        <p className="detail-footnote">{spanish ? "El mapa incluye el resto del país como referencia. La simulación se limita al punto de Guanacaste." : "The map includes the rest of the country for reference. The simulation is limited to the Guanacaste point."}</p>
      </article>
    </div>
  );
}
