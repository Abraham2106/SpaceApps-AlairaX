import { readFileSync } from "node:fs";
import { afterEach, expect, it, vi } from "vitest";
import { loadComparison, publicUrl } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("loads the comparison named by the static catalog", async () => {
  const fetch = vi.fn(async (url: string) => {
    const relativePath = url.slice(publicUrl("").length);
    const path = new URL(`../../public/${relativePath}`, import.meta.url);
    return new Response(readFileSync(path, "utf8"));
  });
  vi.stubGlobal("fetch", fetch);

  const { signal } = new AbortController();
  const result = await loadComparison("", "neutral", signal);
  const file = result.catalog.scenarios.find(({ id }) => id === "neutral")?.resultFile;

  expect(result).toMatchObject({ mode: "static", httpStatus: 200, compare: { scenario_id: "neutral" } });
  expect(fetch).toHaveBeenCalledWith(publicUrl(`data/${file}`), { signal });
});

it("preserves an HTTP comparison error and the live catalog", async () => {
  const zona = { id: "test", name: "Test", latitude: 10.55, longitude: -85.5 };
  const reason = "No hay análogos disponibles";
  const fetch = vi.fn(async (url: string) => {
    switch (url) {
      case "https://example.test/scenarios":
        return Response.json({ _mock: false, zona, scenarios: { neutral: { status: "unavailable", k: 5 } } });
      case "https://example.test/compare":
        return Response.json({ detail: reason }, { status: 409 });
      default:
        return new Response(null, { status: 404 });
    }
  });
  vi.stubGlobal("fetch", fetch);

  const { signal } = new AbortController();
  const result = await loadComparison("https://example.test/", "neutral", signal);

  expect(result).toMatchObject({
    mode: "live", catalog: { zona }, compare: null, httpStatus: 409, httpDetail: reason,
  });
  expect(fetch).toHaveBeenCalledWith("https://example.test/compare", expect.objectContaining({ method: "POST", signal }));
});
