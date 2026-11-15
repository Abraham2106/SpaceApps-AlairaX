// @vitest-environment jsdom
import { createElement } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AgricultureChat } from "./AgricultureChat";
import { askChat, type ChatResponse } from "../lib/chat";
import { useInstrument } from "../store";

vi.mock("../data/queries", () => ({ useCantons: () => ({
  isPending: false, isError: false,
  data: { features: [
    { id: "canas", properties: { name: "Cañas", guanacaste: true } },
    { id: "bagaces", properties: { name: "Bagaces", guanacaste: true } },
    { id: "san-jose", properties: { name: "San José", guanacaste: false } },
  ] },
}) }));
vi.mock("../data/recent", () => ({ useRecentSeasons: () => ({
  data: { seasons: [{ year: 2026 }, { year: 2025 }] },
}) }));
vi.mock("../lib/chat", () => ({ askChat: vi.fn() }));

const response: ChatResponse = {
  answer: "La lluvia disponible es parcial. Revisa la humedad del suelo.", model: "gemini-4-hydrogen", thinking_level: "low",
  context: {
    model_scope: "regional_pilot", _mock: false, generated_at: "2026-11-15T00:00:00Z",
    selection: { canton_ids: ["canas"], start: "2026-10-16", end: "2026-11-14" },
    cantons: [{ id: "canas", status: "partial" }],
    sources: [{ id: "power:canas", url: "https://power.larc.nasa.gov/", provider: "NASA POWER" }],
    warnings: ["Piloto regional, no medición de finca."],
  },
};

function openChat() {
  render(createElement(AgricultureChat));
  fireEvent.click(screen.getByRole("button", { name: "Preguntarle a Guaní" }));
}

beforeEach(() => {
  vi.mocked(askChat).mockReset();
  vi.mocked(askChat).mockResolvedValue(response);
  useInstrument.setState({ selected: ["canas"], scenarioId: "neutral", metric: "modeled_water_deficit_mm", lang: "es", apiBase: "/api", yearA: null, yearB: null });
});
afterEach(cleanup);

describe("Guaní chat", () => {
  it("requires a Guanacaste canton and lets the user choose one", () => {
    useInstrument.setState({ selected: [] });
    openChat();
    expect(screen.getByRole("textbox").hasAttribute("disabled")).toBe(true);
    expect(screen.queryByRole("option", { name: "San José" })).toBeNull();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "canas" } });
    expect(useInstrument.getState().selected).toEqual(["canas"]);
    expect(screen.getByRole("textbox").hasAttribute("disabled")).toBe(false);
  });

  it("sends the displayed canton, scenario and default replay years", async () => {
    openChat();
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "¿Qué debería revisar?" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    await screen.findByText(response.answer);
    expect(askChat).toHaveBeenCalledWith("/api", expect.objectContaining({
      question: "¿Qué debería revisar?", language: "es", history: [],
      selection: { canton_ids: ["canas"], scenario_id: "neutral", metric: "modeled_water_deficit_mm", years: [2026, 2025] },
    }), expect.any(AbortSignal));
    fireEvent.click(screen.getByText("Fuentes de esta respuesta"));
    expect(screen.getByText("NASA POWER")).toBeDefined();
    expect(screen.getByText("Piloto regional, no medición de finca.")).toBeDefined();
  });

  it("aborts and clears the conversation when the selected canton changes", async () => {
    let resolve!: (value: ChatResponse) => void;
    vi.mocked(askChat).mockImplementation(() => new Promise((done) => { resolve = done; }));
    openChat();
    fireEvent.click(screen.getByRole("button", { name: "¿Qué está pasando con el agua?" }));
    const signal = vi.mocked(askChat).mock.calls[0][2];
    expect(screen.getByRole("status").textContent).toContain("Revisando");
    act(() => useInstrument.setState({ selected: ["bagaces"] }));
    expect(signal?.aborted).toBe(true);
    await act(async () => { resolve(response); });
    expect(screen.queryByText(response.answer)).toBeNull();
    expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe("bagaces");
  });

  it("offers retry without duplicating the failed question", async () => {
    vi.mocked(askChat).mockRejectedValueOnce(new Error("private provider detail"));
    openChat();
    fireEvent.click(screen.getByRole("button", { name: "¿Qué está pasando con el agua?" }));
    await screen.findByRole("alert");
    expect(screen.queryByText("private provider detail")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Intentar de nuevo" }));
    await screen.findByText(response.answer);
    expect(screen.getAllByText("¿Qué está pasando con el agua?")).toHaveLength(1);
    expect(askChat).toHaveBeenCalledTimes(2);
  });

  it("restores launcher focus on Escape and preserves transcript on reopen", async () => {
    openChat();
    fireEvent.click(screen.getByRole("button", { name: "¿Cómo se comparan las rotaciones?" }));
    await screen.findByText(response.answer);
    fireEvent.keyDown(window, { key: "Escape" });
    const launcher = screen.getByRole("button", { name: "Preguntarle a Guaní" });
    expect(document.activeElement).toBe(launcher);
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(launcher);
    expect(screen.getByText(response.answer)).toBeDefined();
  });

  it("keeps provider markup as escaped text and uses a speaking mascot after response", async () => {
    vi.mocked(askChat).mockResolvedValueOnce({ ...response, answer: '<script>alert("test")</script> **Cobertura parcial**' });
    openChat();
    fireEvent.click(screen.getByRole("button", { name: "¿Qué limitaciones tienen estos datos?" }));
    await waitFor(() => expect(screen.getByText("Cobertura parcial")).toBeDefined());
    expect(document.querySelector(".nanda-answer script")).toBeNull();
    expect(document.querySelector('.nanda-chat-identity [data-state="speaking"]')).not.toBeNull();
  });
});
