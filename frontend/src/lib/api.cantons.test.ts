import { readFileSync } from "node:fs";
import { afterEach, expect, it, vi } from "vitest";
import { ApiError, loadComparison, publicUrl } from "./api";
import { loadRecentSeasons } from "../data/recent";

afterEach(() => vi.unstubAllGlobals());

const zone = { id: "canas", name: "Cañas", latitude: 10.44154, longitude: -85.10386, validated: false };

function comparison() {
  const result = JSON.parse(readFileSync(new URL("../../public/data/compare-neutral.json", import.meta.url), "utf8"));
  result.zona = { ...zone };
  result.warnings = ["Piloto de Cañas"];
  result.source_refs = ["Cañas source"];
  for (const rotation of result.rotations) {
    for (const run of rotation.runs) run.zona = { ...zone };
  }
  return result;
}

function liveFetch(compareResponse: () => Response) {
  return vi.fn(async (url: string) => {
    switch (url) {
      case "/api/scenarios":
        return Response.json({ _mock: false, zona: { ...zone, id: "provisional-point" }, scenarios: { neutral: { status: "available", k: 5 } } });
      case "/api/chat/cantons":
        return Response.json({ model_scope: "regional_pilot", cantons: { canas: zone } });
      case "/api/cantons/canas/compare":
        return compareResponse();
      default:
        return new Response(null, { status: 404 });
    }
  });
}

it("sends the canonical canton coordinates and keeps the matching simulation metadata", async () => {
  const fetch = liveFetch(() => Response.json(comparison()));
  vi.stubGlobal("fetch", fetch);
  const { signal } = new AbortController();
  const loaded = await loadComparison("/api/", "neutral", signal, "canas");
  expect(loaded).toMatchObject({ httpStatus: 200, catalog: { zona: zone, warnings: ["Piloto de Cañas"], sourceRefs: ["Cañas source"] }, compare: { zona: zone } });
  const request = fetch.mock.calls.find(([url]) => url === "/api/cantons/canas/compare");
  expect(request).toBeDefined();
  const options = (request as unknown as [string, RequestInit])[1];
  expect(options.signal).toBe(signal);
  expect(JSON.parse(options.body as string).zona).toEqual(zone);
  expect(fetch.mock.calls.some(([url]) => url === "/api/compare")).toBe(false);
});

it("keeps a canton failure explicit instead of substituting the original pilot simulation", async () => {
  const fetch = liveFetch(() => Response.json({ detail: "Clima incompleto de Cañas" }, { status: 409 }));
  vi.stubGlobal("fetch", fetch);
  const loaded = await loadComparison("/api", "neutral", undefined, "canas");
  expect(loaded).toMatchObject({ compare: null, httpStatus: 409, httpDetail: "Clima incompleto de Cañas", catalog: { zona: zone } });
  expect(fetch.mock.calls.some(([url]) => url === "/api/compare")).toBe(false);
});

it("rejects a response for a different canton even when its metrics are valid", async () => {
  const other = comparison();
  other.zona.id = "liberia";
  vi.stubGlobal("fetch", liveFetch(() => Response.json(other)));
  const loaded = await loadComparison("/api", "neutral", undefined, "canas");
  expect(loaded).toMatchObject({ compare: null, httpStatus: 502 });
});

it("loads an explicitly exported canton comparison in static mode", async () => {
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith("/cantons/canas/compare-neutral.json")) return Response.json(comparison());
    const relative = url.slice(publicUrl("").length);
    return new Response(readFileSync(new URL(`../../public/${relative}`, import.meta.url), "utf8"));
  });
  vi.stubGlobal("fetch", fetch);
  const loaded = await loadComparison("", "neutral", undefined, "canas");
  expect(loaded.compare?.zona.id).toBe("canas");
  expect(loaded.catalog.zona.id).toBe("canas");
  expect(fetch.mock.calls.some(([url]) => url === publicUrl("data/compare-neutral.json"))).toBe(false);
});

it("does not replace a missing static canton export with the original pilot", async () => {
  const fetch = vi.fn(async (url: string) => {
    if (url.includes("/cantons/")) return new Response(null, { status: 404 });
    const relative = url.slice(publicUrl("").length);
    return new Response(readFileSync(new URL(`../../public/${relative}`, import.meta.url), "utf8"));
  });
  vi.stubGlobal("fetch", fetch);
  await expect(loadComparison("", "neutral", undefined, "canas")).rejects.toMatchObject({ status: 404 });
  expect(fetch.mock.calls.some(([url]) => url === publicUrl("data/compare-neutral.json"))).toBe(false);
});

it("loads recent replays for the same canton and rejects mismatched replay evidence", async () => {
  const fetch = vi.fn(async () => Response.json({ _mock: false, zona: zone, seasons: [] }));
  vi.stubGlobal("fetch", fetch);
  const { signal } = new AbortController();
  await expect(loadRecentSeasons("/api/", "canas", signal)).resolves.toMatchObject({ zona: { id: "canas" } });
  expect(fetch).toHaveBeenCalledWith("/api/cantons/canas/recent", { signal });
  fetch.mockImplementation(async () => Response.json({ _mock: false, zona: { id: "provisional-point" }, seasons: [] }));
  await expect(loadRecentSeasons("/api", "canas")).rejects.toBeInstanceOf(ApiError);
});
