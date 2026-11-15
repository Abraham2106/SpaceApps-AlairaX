import { useMemo, useState, type KeyboardEvent } from "react";
import { useCantons } from "../data/queries";
import { translate } from "../lib/i18n";
import { useInstrument } from "../store";

function searchText(value: string): string {
  return value.toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
}

export function MapCantonList({ query = "", onPick }: { query?: string; onPick?: () => void }) {
  const lang = useInstrument((state) => state.lang);
  const selected = useInstrument((state) => state.selected);
  const toggleCanton = useInstrument((state) => state.toggleCanton);
  const location = useInstrument((state) => state.location);
  const setLocation = useInstrument((state) => state.setLocation);
  const [stopId, setStopId] = useState<string | null>(null);
  const cantons = useCantons();
  const needle = searchText(query.trim());
  const rows = useMemo(() => {
    const features = cantons.data?.features ?? [];
    const ranked = [...features].sort((a, b) => Number(b.properties.guanacaste) - Number(a.properties.guanacaste)
      || a.properties.name.localeCompare(b.properties.name, "es"));
    return ranked.filter(({ properties }) => !needle
      || searchText(properties.name).includes(needle)
      || searchText(properties.sourceName).includes(needle)).slice(0, needle ? 12 : 11);
  }, [cantons.data, needle]);
  const tabStop = rows.find(({ id }) => id === stopId) ?? rows.find(({ id }) => selected.includes(id)) ?? rows[0];

  function onListKey(event: KeyboardEvent<HTMLDivElement>) {
    const options = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[role="option"]'));
    const current = options.indexOf(document.activeElement as HTMLElement);
    let next = -1;
    if (event.key === "ArrowDown") next = Math.min(options.length - 1, current + 1);
    else if (event.key === "ArrowUp") next = Math.max(0, current - 1);
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = options.length - 1;
    if (next < 0 || !options[next]) return;
    event.preventDefault();
    options[next].focus();
  }

  if (!rows.length) {
    if (!needle) return null;
    const message = cantons.isPending ? "map.searchLoading" : cantons.isError ? "map.searchError" : "map.searchEmpty";
    return <p className="map-search-status" role="status">{translate(lang, message)}</p>;
  }

  return (
    <div className="canton-list" role="listbox" aria-multiselectable="true" aria-label={translate(lang, needle ? "map.searchResults" : "common.cantons")} onKeyDown={onListKey}>
      {rows.map((feature) => (
        <button
          key={feature.id}
          type="button"
          role="option"
          aria-selected={selected.includes(feature.id)}
          tabIndex={feature.id === tabStop?.id ? 0 : -1}
          onFocus={() => setStopId(feature.id)}
          onClick={(event) => {
            if (!feature.properties.guanacaste) {
              setLocation(location, { key: "mapReading.noSimulationAvailable", values: { canton: feature.properties.name } });
              return;
            }
            toggleCanton(feature.id, event.shiftKey);
            onPick?.();
          }}
        >
          <span>{feature.properties.name}</span>
          <span className="faint">{feature.properties.guanacaste ? "" : translate(lang, "mapReading.noSimulation")}</span>
        </button>
      ))}
    </div>
  );
}
