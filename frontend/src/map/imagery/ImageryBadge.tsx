import { CalendarDays } from "lucide-react";
import { translate, type MessageKey } from "../../lib/i18n";
import { useInstrument } from "../../store";
import { MODIS_FIRST_DATE, formatGsd, formatImageryDate, isIsoDay, latestImageryDate } from "./catalog";
import type { ImageryChoice, S2Status } from "./selectSource";

const S2_NOTE: Partial<Record<S2Status, MessageKey>> = {
  searching: "imagery.s2Searching",
  none: "imagery.s2None",
  outside: "imagery.s2Outside",
  failed: "imagery.s2Failed",
};

/**
 * Compact source credit. Product details are available through the source panel.
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
  const droneNote: MessageKey | undefined = choice.oam === "failed" ? "imagery.oamFailed" : undefined;
  const note = droneNote ?? (nasaDated && choice.oam !== "active" ? S2_NOTE[choice.s2] : undefined);
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
