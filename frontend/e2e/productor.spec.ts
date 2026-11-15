import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

// Playwright corre desde frontend/. Las capturas van a docs/screenshots del repo,
// o a SCREENSHOT_DIR si se define. ARTIFACTS_DIR guarda una copia extra solo si existe.
const shots = process.env.SCREENSHOT_DIR ?? resolve(process.cwd(), "..", "docs", "screenshots");
const artifacts = process.env.ARTIFACTS_DIR;

test("un productor resuelve las cinco tareas y la consola queda limpia", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });

  await page.goto("/#/");
  await expect(page.getByRole("status").first()).toContainText("PRUEBA");
  await expect(page.getByRole("heading", { name: /déficit hídrico modelado/i })).toBeVisible();
  await page.getByRole("button", { name: "Ir al punto del modelo" }).click();
  await expect(page.getByRole("option", { name: /Liberia/ })).toHaveAttribute("aria-selected", "true");

  await page.getByRole("radio", { name: "Niño fuerte" }).click();
  await expect(page.getByText("Niño fuerte · n = 3")).toBeVisible();
  await expect(page.getByText(/No es rendimiento/).first()).toBeHidden();
  await page.getByText("Leer más").click();
  await expect(page.getByText(/No es rendimiento/).first()).toBeVisible();
  await expect(page.getByText(/no una probabilidad/).first()).toBeVisible();

  await page.getByRole("link", { name: "Confianza" }).click();
  await expect(page.getByRole("heading", { name: "Confianza y procedencia" })).toBeVisible();
  await expect(page.getByText("reviewed: false")).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "NASA POWER" })).toBeVisible();

  await page.getByRole("link", { name: "Mapa" }).click();
  await page.getByRole("button", { name: "Compartir" }).click();
  const share = page.getByRole("dialog");
  const shared = share.locator("textarea");
  await expect(shared).toHaveValue(/fixture/);
  await expect(shared).not.toHaveValue(/ganadora es/);
  await share.getByRole("button", { name: "Cerrar" }).click();

  expect(errors, errors.join("\n")).toEqual([]);
});

test("el teclado alcanza diálogo, escenarios y lista de cantones", async ({ page }) => {
  await page.goto("/#/");
  await expect(page.getByRole("heading", { name: /déficit hídrico modelado/i })).toBeVisible();

  // Diálogo: el foco entra, Tab no se escapa, Escape cierra y el foco vuelve al botón.
  const opener = page.getByRole("button", { name: "Compartir" });
  await opener.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator(":focus")).toHaveCount(1);
  for (let step = 0; step < 6; step += 1) {
    await page.keyboard.press("Tab");
    await expect(dialog.locator(":focus")).toHaveCount(1);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();

  // Escenarios: radiogroup con flechas; un solo botón entra en Tab.
  const strong = page.getByRole("radio", { name: "Niño fuerte" });
  await expect(strong).toHaveAttribute("aria-checked", "true");
  await strong.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: "Neutro" })).toBeChecked();
  await expect(page.getByRole("radio", { name: "Neutro" })).toBeFocused();

  // Métrica: igual.
  await page.getByRole("radio", { name: "Agua" }).focus();
  await page.keyboard.press("End");
  await expect(page.getByRole("radio", { name: "Estrés" })).toBeChecked();

  // Lista de cantones: un solo tope de tabulación y flechas entre opciones.
  const stops = page.locator('[role="option"][tabindex="0"]');
  await expect(stops).toHaveCount(1);
  await stops.focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.locator('[role="option"]').nth(1)).toBeFocused();
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
        mkdirSync(shots, { recursive: true });
        await page.screenshot({ path: resolve(shots, file) });
        if (artifacts) {
          mkdirSync(artifacts, { recursive: true });
          await page.screenshot({ path: resolve(artifacts, file) });
        }
      });
    }
  }
}
