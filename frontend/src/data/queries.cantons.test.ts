// @vitest-environment jsdom
import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useComparison } from "./queries";
import { loadComparison } from "../lib/api";
import { useInstrument } from "../store";
import type { LoadedComparison } from "../lib/types";

vi.mock("../lib/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../lib/api")>(),
  loadComparison: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  useInstrument.setState({ selected: [], apiBase: "/api" });
});

function loaded(id: string): LoadedComparison {
  return {
    mode: "live", compare: null, httpStatus: 200, httpDetail: null,
    catalog: { mock: false, zona: { id, name: id, latitude: 10.5, longitude: -85.2 }, scenarios: [], rotations: [], warnings: [], sourceRefs: [] },
  };
}

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return ({ children }: { children: ReactNode }) => createElement(QueryClientProvider, { client }, children);
}

it("clears the previous canton while the newly selected simulation loads", async () => {
  useInstrument.setState({ selected: ["canas"], apiBase: "/api", scenarioId: "neutral" });
  let finish!: (value: LoadedComparison) => void;
  vi.mocked(loadComparison).mockImplementation(async (_base, _scenario, _signal, cantonId) => {
    if (cantonId === "canas") return loaded("canas");
    return new Promise((resolve) => { finish = resolve; });
  });
  const { result } = renderHook(() => useComparison(), { wrapper: wrapper() });
  await waitFor(() => expect(result.current.data?.catalog.zona.id).toBe("canas"));
  act(() => useInstrument.setState({ selected: ["bagaces", "canas"] }));
  await waitFor(() => expect(loadComparison).toHaveBeenLastCalledWith("/api", "neutral", expect.any(AbortSignal), "bagaces"));
  expect(result.current.data).toBeUndefined();
  expect(result.current.isPending).toBe(true);
  await act(async () => finish(loaded("bagaces")));
  await waitFor(() => expect(result.current.data?.catalog.zona.id).toBe("bagaces"));
});

it("aborts an obsolete canton request and ignores a late response", async () => {
  useInstrument.setState({ selected: ["canas"], apiBase: "/api", scenarioId: "neutral" });
  let oldSignal: AbortSignal | undefined;
  let finishOld!: (value: LoadedComparison) => void;
  vi.mocked(loadComparison).mockImplementation(async (_base, _scenario, signal, cantonId) => {
    if (cantonId !== "canas") return loaded(cantonId!);
    oldSignal = signal;
    return new Promise((resolve) => { finishOld = resolve; });
  });
  const { result } = renderHook(() => useComparison(), { wrapper: wrapper() });
  await waitFor(() => expect(oldSignal).toBeDefined());
  act(() => useInstrument.setState({ selected: ["bagaces"] }));
  await waitFor(() => expect(result.current.data?.catalog.zona.id).toBe("bagaces"));
  expect(oldSignal?.aborted).toBe(true);
  await act(async () => finishOld(loaded("canas")));
  expect(result.current.data?.catalog.zona.id).toBe("bagaces");
});
