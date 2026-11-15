import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, publicUrl } from "../lib/api";
import { daily } from "../lib/schemas";
import { useInstrument } from "../store";

const recentSchema = z.object({
  _mock: z.literal(false),
  zona: z.object({ id: z.string() }).optional(),
  seasons: z.array(z.object({
    year: z.number().int(),
    start: z.string(),
    end: z.string(),
    complete: z.boolean(),
    runs: z.array(z.object({
      rotation_id: z.enum(["rice_melon", "rice_legume", "rice_sorghum"]),
      daily_balance: z.array(daily),
    })),
  })),
});

export function useRecentSeasons() {
  const apiBase = useInstrument((state) => state.apiBase);
  const cantonId = useInstrument((state) => state.selected[0]);
  return useQuery({
    queryKey: ["recent-seasons", apiBase, cantonId ?? null],
    staleTime: apiBase && cantonId ? 30_000 : Infinity,
    retry: false,
    queryFn: ({ signal }) => loadRecentSeasons(apiBase, cantonId, signal),
  });
}

export async function loadRecentSeasons(apiBase: string, cantonId?: string, signal?: AbortSignal) {
  const url = cantonId
    ? apiBase
      ? `${apiBase.replace(/\/$/, "")}/cantons/${encodeURIComponent(cantonId)}/recent`
      : publicUrl(`data/cantons/${encodeURIComponent(cantonId)}/recent-seasons.json`)
    : publicUrl("data/recent-seasons.json");
  const response = await fetch(url, { signal });
  if (!response.ok) throw new ApiError(response.status, "No se pudieron cargar las temporadas del cantón seleccionado.");
  const recent = recentSchema.parse(await response.json());
  if (cantonId && recent.zona?.id !== cantonId) {
    throw new ApiError(502, "Las temporadas recibidas no corresponden al cantón seleccionado.");
  }
  return recent;
}
