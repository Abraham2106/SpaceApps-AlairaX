import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { publicUrl } from "../lib/api";
import { daily } from "../lib/schemas";

const recentSchema = z.object({
  _mock: z.literal(false),
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
  return useQuery({
    queryKey: ["recent-seasons"],
    staleTime: Infinity,
    queryFn: async ({ signal }) => {
      const response = await fetch(publicUrl("data/recent-seasons.json"), { signal });
      if (!response.ok) throw new Error("Recent seasons could not be loaded");
      return recentSchema.parse(await response.json());
    },
  });
}
