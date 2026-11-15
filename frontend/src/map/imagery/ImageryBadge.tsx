import { CalendarDays } from "lucide-react";
import { translate, type MessageKey } from "../../lib/i18n";
import { useInstrument } from "../../store";
import { MODIS_FIRST_DATE, formatGsd, formatImageryDate, isIsoDay, latestImageryDate } from "./catalog";
import type { HlsStatus, ImageryChoice, S2Status } from "./selectSource";

const HLS_NOTE: Partial<Record<HlsStatus, MessageKey>> = {
  too_recent: "imagery.hlsTooRecent",
  before_mission: "imagery.hlsBeforeMission",
  failed: "imagery.hlsFailed",
};

const S2_NOTE: Partial<Record<S2Status, MessageKey>> = {
  searching: "imagery.s2Searching",
  none: "imagery.s2None",
  outside: "imagery.s2Outside",
  failed: "imagery.s2Failed",
};

/**
 * Ficha de procedencia: siempre dice de quién es la imagen, qué resolución tiene
 * y de qué día es, o que el proveedor no publica la fecha.
 */
export function ImageryBadge({ choice }: { choice: ImageryChoice }) {
  const lang = useInstrument((state) => state.lang);
  const basemap = useInstrument((state) => state.basemap);
  const imageryDate = useInstrument((state) => state.imageryDate);
  const setImageryDate = useInstrument((state) => state.setImageryDate);
  const nasaDated = basemap === "modis";
  const drone = choice.drone;
  const summary: MessageKey = choice.primary === "oam" && drone
    ? "imagery.oam"
    : choice.primary === "s2"
    ? "imagery.s2"
    : choice.fallback
      ? "imagery.esriFallback"
      : choice.primary === "esri"
        ? "imagery.esri"
        : choice.primary === "marble"
          ? "imagery.marble"
          : choice.primary === "hls"
            ? choice.layers.includes("modis") ? "imagery.hlsOverModis" : "imagery.hls"
            : "imagery.modis";
  // El dron tapa lo de debajo: con dron en pantalla no se explican HLS ni Sentinel-2.
  // Sentinel-2 manda sobre HLS: si se buscó una escena, la nota explica esa búsqueda.
  const droneNote: MessageKey | undefined = choice.oam === "failed" ? "imagery.oamFailed" : undefined;
  const nasaNote = choice.oam === "active"
    ? undefined
    : S2_NOTE[choice.s2] ?? (choice.s2 === "active" ? undefined : HLS_NOTE[choice.hls]);
  const note = droneNote ?? (nasaDated ? nasaNote : undefined);
  const scene = choice.scene;
  const values = {
    date: formatImageryDate(drone?.date ?? scene?.date ?? imageryDate, lang),
    provider: drone?.provider ?? "",
    resolution: formatGsd(drone?.gsdM ?? null, lang) ?? translate(lang, "imagery.resolutionUnknown"),
    license: drone?.license ?? "",
    cloud: scene?.cloudCover == null ? translate(lang, "imagery.cloudUnknown") : `${Math.round(scene.cloudCover)} %`,
    id: scene?.id ?? "",
  };
  return (
    <div className="imagery-badge" role="group" aria-label={translate(lang, "imagery.label")} data-source={choice.primary}>
      <span className="imagery-badge-text">{translate(lang, summary, values)}</span>
      {nasaDated ? (
        <label className="imagery-date">
          <CalendarDays size={14} strokeWidth={1.5} aria-hidden />
          <input
            type="date"
            value={imageryDate}
            min={MODIS_FIRST_DATE}
            max={latestImageryDate()}
            aria-label={translate(lang, "imagery.dateLabel")}
            onChange={(event) => {
              if (isIsoDay(event.target.value)) setImageryDate(event.target.value);
            }}
          />
        </label>
      ) : null}
      {note ? <span className="imagery-note" role="status">{translate(lang, note)}</span> : null}
    </div>
  );
}
