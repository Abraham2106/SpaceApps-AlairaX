import { useEffect, useRef } from "react";
import plates from "../geo/plates.json";
import { useInstrument } from "../store";
import { useCantons, useComparison } from "../data/queries";
import { cantonAt } from "../lib/geo";

export function CantonsScreen() {
  const lang = useInstrument((state) => state.lang);
  const spanish = lang === "es";
  const selectOnly = useInstrument((state) => state.selectOnly);
  const selected = useInstrument((state) => state.selected);
  const comparison = useComparison();
  const cantons = useCantons();
  const root = useRef<HTMLDivElement>(null);
  const zona = comparison.data?.compare?.zona ?? comparison.data?.catalog.zona;
  const point = zona && cantons.data ? cantonAt(zona.longitude, zona.latitude, cantons.data) : null;

  useEffect(() => {
    const node = root.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible?.target.id) return;
        if (useInstrument.getState().selected[0] !== visible.target.id) selectOnly(visible.target.id);
      },
      { root: node, threshold: 0.55 },
    );
    node.querySelectorAll("section[id]").forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [selectOnly]);

  return (
    <div className="atlas" ref={root}>
      <div className="atlas-spacer">
        <p className="scroll-hint">{spanish ? "Deslizá para ver cada cantón, separado." : "Scroll to see each canton, on its own."}</p>
      </div>
      {plates.map((plate, index) => (
        <section
          className={index % 2 === 0 ? "plate" : "plate plate-alt"}
          id={plate.id}
          key={plate.id}
          aria-current={selected[0] === plate.id ? "true" : undefined}
        >
          <svg viewBox="0 0 100 100" role="img" aria-label={plate.name}>
            <path className="plate-outline" d={plate.path} fill={plate.tint} strokeWidth="0.6" />
          </svg>
          <div>
            <p className="kicker">{spanish ? `Cantón ${index + 1} de 11` : `Canton ${index + 1} of 11`}</p>
            <h2>{plate.name}</h2>
            <p>
              {spanish
                ? "Dentro de Guanacaste, la provincia del punto provisional. Esta placa no tiene una simulación propia. El color distingue el límite, no una métrica."
                : "Inside Guanacaste, the province of the provisional point. This plate has no simulation of its own. The color separates the boundary, not a metric."}
            </p>
            {point?.id === plate.id ? (
              <p>
                {spanish
                  ? `El punto ${zona?.latitude}, ${zona?.longitude} cae en este polígono de geoBoundaries. Sigue siendo un punto de trabajo, no una finca confirmada.`
                  : `The point ${zona?.latitude}, ${zona?.longitude} falls in this geoBoundaries polygon. It is still a working point, not a confirmed farm.`}
              </p>
            ) : null}
            <p className="plate-meta">
              {plate.center[1].toFixed(3)}, {plate.center[0].toFixed(3)} · {plate.sourceName}
            </p>
            <button onClick={() => selectOnly(plate.id)}>{spanish ? "Centrar en el mapa" : "Center on the map"}</button>
          </div>
        </section>
      ))}
      <section className="plate" id="fuera">
        <div>
          <p className="kicker">{spanish ? "El resto del país" : "The rest of the country"}</p>
          <h2>{spanish ? "Sin simulación disponible" : "No simulation available"}</h2>
          <p>
            {spanish
              ? "Los otros cantones de la capa se pueden ver en el mapa. Tocarlo no inventa un resultado. El modelo no se extrapola fuera de Guanacaste."
              : "The other cantons in the layer are visible on the map. Touching one does not invent a result. The model is not extrapolated outside Guanacaste."}
          </p>
        </div>
      </section>
    </div>
  );
}
