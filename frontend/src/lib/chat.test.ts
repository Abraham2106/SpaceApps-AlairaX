import { afterEach, expect, it, vi } from "vitest";
import { askChat, loadChatContext } from "./chat";

afterEach(() => vi.unstubAllGlobals());

const selection = { canton_ids: ["canas"], start: "2025-01-01", end: "2025-01-07", scenario_id: "neutral" as const, years: [2025] };
const context = {
  model_scope: "regional_pilot", _mock: false, generated_at: "2026-11-15T16:00:00+00:00",
  selection,
  cantons: [{ id: "canas", status: "partial", summary: { precipitation_mm: { total: 1.22, available_days: 6, expected_days: 7, complete: false } }, daily: [{ date: "2025-01-01", precipitation_mm: null }], units: { precipitation_mm: "mm/day" } }],
  sources: [{ id: "power:canas", url: "https://power.larc.nasa.gov/", provider: "NASA POWER" }],
  warnings: ["Piloto regional; faltantes no son cero."],
};

it("sends selected simulation context and conversation through our server without provider credentials", async () => {
  const fetch = vi.fn(async () => Response.json({ answer: "La cobertura es parcial.", model: "gemini-4-hydrogen", thinking_level: "low", context }));
  vi.stubGlobal("fetch", fetch);
  const { signal } = new AbortController();
  const request = { question: "¿Qué significa?", selection, history: [{ role: "user" as const, content: "Tengo arroz" }], farm: { crop: "arroz" }, language: "es" as const };
  const result = await askChat("/api/", request, signal);
  expect(fetch).toHaveBeenCalledWith("/api/chat", { method: "POST", signal, headers: { "content-type": "application/json" }, body: JSON.stringify(request) });
  expect(result.context).toEqual(context);
  expect(result.context.cantons[0].daily).toEqual([{ date: "2025-01-01", precipitation_mm: null }]);
});

it("fetches verifiable evidence without requesting a model answer", async () => {
  const fetch = vi.fn(async () => Response.json(context));
  vi.stubGlobal("fetch", fetch);
  const result = await loadChatContext("/api", selection);
  expect(fetch).toHaveBeenCalledWith("/api/chat/context", expect.objectContaining({ body: JSON.stringify(selection) }));
  expect(result.sources).toEqual(context.sources);
  expect(result.warnings).toEqual(context.warnings);
});

it("preserves safe server errors and rejects malformed successful responses", async () => {
  const fetch = vi.fn(async () => Response.json({ detail: "Gemini no pudo atender la consulta." }, { status: 429 }));
  vi.stubGlobal("fetch", fetch);
  await expect(askChat("/api", { question: "Ayuda", selection })).rejects.toMatchObject({ status: 429, detail: "Gemini no pudo atender la consulta." });
  fetch.mockImplementation(async () => Response.json({ answer: "Sin contexto" }));
  await expect(askChat("/api", { question: "Ayuda", selection })).rejects.toMatchObject({ status: 502 });
});

it("requires a backend and rejects unsupported input before any network request", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  await expect(askChat("", { question: "Ayuda", selection })).rejects.toMatchObject({ status: 503 });
  await expect(askChat("/api", { question: "Ayuda", selection: { canton_ids: ["canas", "canas"] } })).rejects.toThrow();
  expect(fetch).not.toHaveBeenCalled();
});

it("rejects otherwise valid answers associated with another selection or year", async () => {
  const fetch = vi.fn(async () => Response.json({
    answer: "Resultados", model: "gemini-4-hydrogen", thinking_level: "low",
    context: { ...context, selection: { ...selection, years: [2024] } },
  }));
  vi.stubGlobal("fetch", fetch);
  await expect(askChat("/api", { question: "Ayuda", selection })).rejects.toMatchObject({ status: 502 });
  fetch.mockImplementation(async () => Response.json({ ...context, cantons: [{ id: "liberia", status: "available" }] }));
  await expect(loadChatContext("/api", selection)).rejects.toMatchObject({ status: 502 });
});
