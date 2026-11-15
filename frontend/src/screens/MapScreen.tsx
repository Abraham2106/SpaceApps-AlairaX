import { translate } from "../lib/i18n";
import { useRef, useState } from "react";
import { Search } from "lucide-react";
import { formatNumber } from "../lib/format";
import { surfaceColor, surfaceDomain, useSurface } from "../lib/surface";
import { isCantonBoundaryMessage, useInstrument } from "../store";
import { MapLayers } from "../map/MapLayers";
import { MapReading } from "../map/MapReading";
import { MapCantonList } from "../map/MapCantonList";

export function MapScreen() {
  const lang = useInstrument((state) => state.lang);
  const mesh = useInstrument((state) => state.overlays.hex);
  const locationMessage = useInstrument((state) => state.locationMessage);
  const [query, setQuery] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const surface = useSurface();
  const [min, max] = surfaceDomain(surface.data);
  const boundaryMessage = isCantonBoundaryMessage(locationMessage) ? locationMessage : null;

  function clearBoundaryMessage() {
    if (boundaryMessage) {
      const { location, setLocation } = useInstrument.getState();
      setLocation(location, null);
    }
  }

  return (
    <>
      <form className="map-search" role="search" onSubmit={(event) => {
        event.preventDefault();
        event.currentTarget.querySelector<HTMLElement>('[role="option"][tabindex="0"]')?.focus();
      }} onKeyDown={(event) => {
        if (event.key !== "Escape" || (!query && !boundaryMessage)) return;
        event.preventDefault();
        setQuery("");
        clearBoundaryMessage();
        input.current?.focus();
      }}>
        <Search size={16} strokeWidth={1.5} aria-hidden />
        <input ref={input} className="search" value={query} onChange={(event) => {
          setQuery(event.target.value);
          clearBoundaryMessage();
        }} placeholder={translate(lang, "map.findCanton")} aria-label={translate(lang, "map.findCanton")} />
        {query.trim() || boundaryMessage ? (
          <div className="map-search-results">
            {query.trim() ? <MapCantonList query={query} onPick={() => { setQuery(""); input.current?.focus(); }} /> : null}
            {boundaryMessage ? <p className="map-search-status" role="status">{translate(lang, boundaryMessage.key, boundaryMessage.values)}</p> : null}
          </div>
        ) : null}
      </form>
      <MapReading />
      <MapLayers />
      {mesh && surface.data ? <div className="map-legend" role="group" aria-label={translate(lang, "map.scale")}>
        <div className="legend-top">
          <span>{formatNumber(min, lang, 0)}</span>
          <span>{translate(lang, "map.sampleFiguresRiceMelon")}</span>
          <span>{formatNumber(max, lang, 0)}</span>
        </div>
        <div className="legend">
          {Array.from({ length: 32 }, (_, index) => (
            <span key={index} style={{ background: surfaceColor(min + ((max - min) * index) / 31, min, max) }} />
          ))}
        </div>
      </div> : null}
    </>
  );
}
