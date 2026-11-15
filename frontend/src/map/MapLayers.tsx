import { translate } from "../lib/i18n";
import { useState } from "react";
import { Box, Globe2, Hexagon, Layers, Mountain, Pentagon, Route, Satellite, ScanLine } from "lucide-react";
import { Dialog } from "../components/Dialog";
import { useInstrument } from "../store";

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

export function MapLayers() {
  const lang = useInstrument((state) => state.lang);
  const basemap = useInstrument((state) => state.basemap);
  const setBasemap = useInstrument((state) => state.setBasemap);
  const overlays = useInstrument((state) => state.overlays);
  const toggleOverlay = useInstrument((state) => state.toggleOverlay);
  const [layersOpen, setLayersOpen] = useState(false);

  const layerButtons = (
    <>
      {([
        ["satellite", translate(lang, "mapLayers.photo")],
        ["modis", translate(lang, "mapLayers.nasa")],
        ["marble", translate(lang, "mapLayers.marble")],
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
        ["cantons", translate(lang, "common.cantons")],
        ["hex", translate(lang, "mapLayers.mesh")],
        ["terrain", translate(lang, "mapLayers.relief")],
        ["plates", translate(lang, "mapLayers.height")],
        ["osm", translate(lang, "mapLayers.roads")],
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
      <button className="layers-fab" type="button" aria-haspopup="dialog" onClick={() => setLayersOpen(true)}><Layers size={18} strokeWidth={1.5} aria-hidden /> {translate(lang, "mapLayers.layers")}</button>
      <div className="hud right-hud hide-mobile" role="toolbar" aria-label={translate(lang, "mapLayers.layers")}>
        {layerButtons}
      </div>
      {layersOpen ? (
        <Dialog labelledBy="layers-title" onClose={() => setLayersOpen(false)}>
          <h2 id="layers-title">{translate(lang, "mapLayers.layers")}</h2>
          <div className="layer-grid">{layerButtons}</div>
          <p className="faint">{translate(lang, "mapLayers.eachHexagonCopiesSyntheticValue")}</p>
          <button type="button" onClick={() => setLayersOpen(false)}>{translate(lang, "common.close")}</button>
        </Dialog>
      ) : null}
    </>
  );
}
