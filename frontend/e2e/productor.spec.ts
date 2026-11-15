import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";

const shots = "/agent/repos/spaceapps-alairax/docs/screenshots";
const artifacts = "/opt/cursor/artifacts";

test.beforeAll(() => {
  mkdirSync(shots, { recursive: true });
  mkdirSync(artifacts, { recursive: true });
});

test("un productor resuelve las cinco tareas y la consola queda limpia", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });

  await page.goto("/#/");
  await expect(page.getByRole("status").first()).toContainText("FIXTURE");
  await expect(page.getByRole("heading", { name: /déficit hídrico modelado/i })).toBeVisible();
  await page.getByRole("button", { name: "Ir al punto del modelo" }).click();
  await expect(page.getByRole("option", { name: /Liberia/ })).toHaveAttribute("aria-selected", "true");

  await page.getByRole("button", { name: "Niño fuerte" }).click();
  await expect(page.getByText("Niño fuerte · n = 3")).toBeVisible();
  await expect(page.getByText(/No es rendimiento/).first()).toBeHidden();
  await page.getByText("Leer la frase completa").click();
  await expect(page.getByText(/No es rendimiento/).first()).toBeVisible();
  await expect(page.getByText(/no una probabilidad/).first()).toBeVisible();

  await page.getByRole("link", { name: "Confianza" }).click();
  await expect(page.getByRole("heading", { name: "Confianza y procedencia" })).toBeVisible();
  await expect(page.getByText("reviewed: false")).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "NASA POWER" })).toBeVisible();

  await page.getByRole("link", { name: "Mapa" }).click();
  await page.getByRole("button", { name: "Compartir" }).click();
  const share = page.getByRole("dialog");
  await expect(share).toContainText("fixture");
  await expect(share).not.toContainText("ganadora es");
  await share.getByRole("button", { name: "Cerrar" }).click();

  expect(errors, errors.join("\n")).toEqual([]);
});

const views = [
  ["map", "/#/"],
  ["cantons", "/#/cantones"],
  ["rotations", "/#/rotaciones"],
  ["season", "/#/temporada"],
  ["trust", "/#/confianza"],
] as const;

for (const [name, path] of views) {
  for (const [theme, themeName] of [["night", "Noche"], ["sun", "Sol"]] as const) {
    for (const [width, height, size] of [[360, 740, "360"], [768, 1024, "768"], [1440, 900, "desktop"]] as const) {
      test(`captura ${name} ${theme} ${size}`, async ({ page }) => {
        await page.setViewportSize({ width, height });
        await page.goto(path);
        if (theme === "sun") await page.getByRole("button", { name: "Noche" }).click();
        if (name === "rotations") await page.getByRole("table").first().waitFor();
        if (name === "season") await page.getByRole("heading", { name: /temporada|season/i }).waitFor();
        if (name === "trust") await page.getByRole("rowheader", { name: "NASA POWER" }).waitFor();
        if (name === "map" || name === "cantons") await page.getByText("10.55").first().waitFor();
        await page.waitForTimeout(name === "map" || name === "cantons" ? 5000 : 300);
        const file = `${name}-${theme}-${size}.png`;
        await page.screenshot({ path: `${shots}/${file}` });
        await page.screenshot({ path: `${artifacts}/${file}` });
      });
    }
  }
}
