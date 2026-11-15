import { useQuery } from "@tanstack/react-query";
import { loadComparison, publicUrl } from "../lib/api";
import type { CantonCollection } from "../lib/geo";
import { useInstrument } from "../store";

export function useCantons() {
  return useQuery({
    queryKey: ["cantons"],
    staleTime: Infinity,
    queryFn: async ({ signal }) => {
      const response = await fetch(publicUrl("geo/cantons.geojson"), { signal });
      if (!response.ok) throw new Error("No se pudo leer la capa de cantones.");
      return (await response.json()) as CantonCollection;
    },
  });
}

export function useComparison() {
  const scenarioId = useInstrument((state) => state.scenarioId);
  const apiBase = useInstrument((state) => state.apiBase);
  // With multiple map selections, the first selected canton drives the detail
  // panels. The same primary canton is used by recent-season replays.
  const cantonId = useInstrument((state) => state.selected[0]);
  return useQuery({
    queryKey: ["comparison", apiBase, scenarioId, cantonId ?? null],
    staleTime: 30_000,
    retry: false,
    queryFn: ({ signal }) => loadComparison(apiBase, scenarioId, signal, cantonId),
  });
}
