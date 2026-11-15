import { CalendarDays } from "lucide-react";
import { translate, type MessageKey } from "../../lib/i18n";
import { useInstrument } from "../../store";
import { MODIS_FIRST_DATE, formatImageryDate, isIsoDay, latestImageryDate } from "./catalog";
import type { HlsStatus, ImageryChoice } from "./selectSource";

const HLS_NOTE: Partial<Record<HlsStatus, MessageKey>> = {
  too_recent: "imagery.hlsTooRecent",
  before_mission: "imagery.hlsBeforeMission",
  failed: "imagery.hlsFailed",
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
  const summary: MessageKey = choice.fallback
    ? "imagery.esriFallback"
    : choice.primary === "esri"
      ? "imagery.esri"
      : choice.primary === "marble"
        ? "imagery.marble"
        : choice.primary === "hls"
          ? choice.layers.includes("modis") ? "imagery.hlsOverModis" : "imagery.hls"
          : "imagery.modis";
  const hlsNote = HLS_NOTE[choice.hls];
  return (
    <div className="imagery-badge" role="group" aria-label={translate(lang, "imagery.label")} data-source={choice.primary}>
      <span className="imagery-badge-text">{translate(lang, summary, { date: formatImageryDate(imageryDate, lang) })}</span>
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
      {hlsNote && nasaDated ? <span className="imagery-note" role="status">{translate(lang, hlsNote)}</span> : null}
    </div>
  );
}
