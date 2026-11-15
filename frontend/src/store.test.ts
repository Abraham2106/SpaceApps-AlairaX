import { expect, it } from "vitest";
import { initialApiBase } from "./store";

it("en desarrollo, sin VITE_API_URL, la interfaz usa el proxy /api", () => {
  const configured = (import.meta.env.VITE_API_URL ?? "").trim();
  if (configured) {
    expect(initialApiBase()).toBe(configured);
    return;
  }
  expect(import.meta.env.DEV).toBe(true);
  expect(initialApiBase()).toBe("/api");
});
