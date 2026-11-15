import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import type { CompareResponse } from "../src/lib/types";

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
  await expect(page.getByRole("heading", { name: "Agua que faltó" })).toBeVisible();
  await page.getByRole("button", { name: "Ir al punto del modelo" }).click();
  await expect(page.getByRole("option", { name: /Liberia/ })).toHaveAttribute("aria-selected", "true");

  await page.getByRole("radio", { name: "Niño fuerte" }).click();
  await expect(page.locator(".reading-lead")).toContainText("en el punto del modelo");
  const modeledValue = await page.locator(".readout").innerText();
  await page.getByRole("option", { name: "Cañas" }).click();
  await expect(page.locator(".readout")).toHaveText(modeledValue, { useInnerText: true });
  await expect(page.getByText(/Las cifras no indican rendimiento/)).toBeHidden();
  await page.getByText("Leer más").click();
  await expect(page.getByText(/Las cifras no indican rendimiento/)).toBeVisible();
  await expect(page.getByText(/no es una probabilidad/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Limitaciones", exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Confianza" }).click();
  await expect(page.getByRole("heading", { name: "Confianza y procedencia" })).toBeVisible();
  await expect(page.getByText("reviewed: false")).toBeVisible();
  await expect(page.getByRole("heading", { name: "NASA POWER" })).toBeVisible();

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
  await expect(page.getByRole("heading", { name: "Agua que faltó" })).toBeVisible();

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

test("el reproductor y los controles del mapa caben a 768 px", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto("/#/");
  await page.getByRole("button", { name: "Noche" }).click();

  const slider = page.getByRole("slider", { name: "Temporada, abril a diciembre" });
  const compareYears = page.getByRole("button", { name: "Comparar años" });
  await expect(page.getByRole("button", { name: "Capas", exact: true })).toBeVisible();
  expect((await slider.boundingBox())?.width).toBeGreaterThanOrEqual(240);
  await expect(compareYears).toHaveCSS("white-space", "nowrap");
  await compareYears.click();
  await expect(page.getByText(/Balance diario: sin dato/)).toBeVisible();

  const overlaps = await page.evaluate(() => {
    const controls = Array.from(document.querySelectorAll(".map-search, .map-legend, .right-hud, .left-hud, .year-pop"));
    return controls.flatMap((control, index) => {
      const box = control.getBoundingClientRect();
      return controls.slice(index + 1).filter((other) => {
        const next = other.getBoundingClientRect();
        return box.right > next.left && box.left < next.right && box.bottom > next.top && box.top < next.bottom;
      }).map((other) => [control.className, other.className]);
    });
  });
  expect(overlaps).toEqual([]);

  const player = await page.locator(".player").boundingBox();
  const attribution = await page.locator(".attrib").boundingBox();
  expect(player!.y + player!.height).toBeLessThan(attribution!.y);
});

test("Rotaciones ofrece carga, tooltips por teclado y tabla a 360 px", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  let release = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/data/compare-strong_el_nino.json", async (route) => {
    await held;
    const response = await route.fetch();
    const data = await response.json() as CompareResponse;
    const level = data.rotations.find(({ rotation_id }) => rotation_id === "rice_legume");
    if (level) level.metrics.modeled_water_deficit_mm.p50 = null;
    await route.fulfill({ response, json: data });
  });

  try {
    await page.goto("/#/rotaciones");
    await expect(page.getByRole("status").filter({ hasText: "Cargando la comparación" })).toBeVisible();
    await expect(page.locator(".comparison-skeleton")).toBeVisible();
  } finally {
    release();
  }

  const picker = page.getByRole("radio", { name: "Gráfico", exact: true });
  const difference = page.getByRole("region", { name: "Diferencia frente a Arroz → melón" });
  await expect(difference).toBeVisible();
  await expect(page.locator(".comparison-skeleton")).toHaveCount(0);
  await expect(page.getByRole("table")).toHaveCount(0);

  await picker.focus();
  await page.keyboard.press("Tab");
  const reference = difference.getByRole("button", { name: /^Arroz → melón/ });
  await expect(reference).toBeFocused();
  await expect(reference).toHaveAccessibleDescription(/Mediana \(p50\) 0 mm/);
  await expect(page.getByRole("tooltip")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("tooltip")).toHaveCount(0);

  const modeled = page.getByRole("region", { name: "Valores modelados por rotación" });
  const legume = modeled.getByRole("button", { name: /Arroz → leguminosa/ });
  await expect(legume).toContainText("sin dato");
  await legume.hover();
  await expect(page.getByRole("tooltip")).toContainText("Por año");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("tooltip")).toHaveCount(0);

  await picker.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: "Tabla", exact: true })).toBeChecked();
  await expect(difference).toHaveCount(0);
  await expect(page.getByRole("table", { name: "Valores modelados por rotación" }).getByRole("cell", { name: "sin dato" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Valores modelados por año" })).toBeVisible();
  const hasOverflow = await page.locator(".screen").evaluate((element) => element.scrollWidth > element.clientWidth + 1);
  expect(hasOverflow).toBe(false);
});

test("la fase 6 conserva las fechas provisionales y la navegación de los cantones", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  await page.goto("/#/temporada");
  await expect(page.getByText("verified: false")).toBeVisible();
  await expect(page.getByText("Balance diario: sin dato")).toBeVisible();
  const firstYear = page.getByLabel("Año A", { exact: true });
  const secondYear = page.getByLabel("Año B", { exact: true });
  await expect(firstYear).toBeVisible();
  await expect(secondYear).toBeVisible();
  await expect(firstYear.getByRole("option", { name: "2026" })).toHaveCount(0);
  const year = await secondYear.inputValue();
  await firstYear.selectOption(year);
  await expect(page.getByRole("columnheader", { name: "A · " + year })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "B · " + year })).toBeVisible();

  await page.getByRole("link", { name: "Confianza", exact: true }).click();
  await expect(page.getByText("reviewed: false")).toBeVisible();
  await expect(page.getByRole("heading", { name: "NASA POWER" })).toBeVisible();
  const address = page.getByLabel("Dirección de la API");
  await address.fill("api-invalida");
  await address.press("Enter");
  await expect(page.getByRole("alert")).toContainText("La dirección debe empezar");
  await address.clear();
  await address.press("Enter");
  await expect(page.getByText("Se activaron los datos de prueba.")).toBeVisible();

  await page.getByRole("link", { name: "Cantones", exact: true }).click();
  const canton = page.getByLabel("Elegir cantón");
  await expect(canton.getByRole("option")).toHaveCount(11);
  await canton.selectOption({ label: "Cañas" });
  await expect(page.getByRole("img", { name: "Límite de Cañas" })).toBeVisible();
  await page.getByRole("link", { name: "Ver cantón en el mapa" }).click();
  await expect(page.getByRole("option", { name: "Cañas", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".readout")).toContainText("120 mm");
});

test("la fase 7 traduce los avisos activos y descarga el mapa al abrirlo", async ({ page }) => {
  const mapAssets: string[] = [];
  const mapAsset = /\/assets\/NandaMap-[^/]+\.(?:js|css)$/;
  page.on("request", (request) => {
    if (mapAsset.test(new URL(request.url()).pathname)) mapAssets.push(request.url());
  });
  let release = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  await page.route(/\/assets\/NandaMap-[^/]+\.js$/, async (route) => {
    await held;
    await route.continue();
  });

  try {
    await page.goto("/#/confianza");
    await expect(page.getByText("reviewed: false")).toBeVisible();
    await expect(page.getByRole("application")).toHaveCount(0);
    expect(mapAssets).toEqual([]);

    const address = page.getByLabel("Dirección de la API");
    await address.fill("api-invalida");
    await address.press("Enter");
    await expect(page.getByRole("alert")).toContainText("La dirección debe empezar");
    await page.getByRole("button", { name: /Cambiar a inglés/ }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.getByRole("heading", { name: "Trust and provenance" })).toBeVisible();
    await expect(page.getByRole("alert")).toContainText("The address must start");
    expect(mapAssets).toEqual([]);

    await page.getByRole("link", { name: "Map", exact: true }).click();
    await expect(page.getByText("Loading the map…")).toBeVisible();
    await expect.poll(() => mapAssets.length).toBeGreaterThan(0);
  } finally {
    release();
  }

  await expect(page.getByRole("application", { name: /^Map of Costa Rica/ })).toBeVisible();
  await page.getByRole("button", { name: "Share", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Text to share" })).toHaveValue(/Strong El Niño/);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: /Switch to Spanish/ }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "es");
  await expect(page.getByRole("application", { name: /^Mapa de Costa Rica/ })).toBeVisible();
});

test("Saltar al contenido lleva el foco al área principal sin cambiar de ruta", async ({ page }) => {
  await page.goto("/#/confianza");
  await expect(page.getByRole("heading", { name: "Confianza y procedencia" })).toBeVisible();
  await expect(page).toHaveURL(/#\/confianza\?/);
  const route = page.url();
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Saltar al contenido" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await expect(page).toHaveURL(route);
});

test("captura rotations error desktop y recupera al reintentar", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.route("**/data/compare-strong_el_nino.json", (route) => route.fulfill({ status: 503 }), { times: 1 });
  await page.goto("/#/rotaciones");
  await expect(page.getByRole("alert")).toContainText("No se pudo leer la comparación");
  mkdirSync(shots, { recursive: true });
  await page.screenshot({ path: resolve(shots, "rotations-error-desktop.png") });
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page.getByRole("region", { name: /Diferencia frente a/ })).toBeVisible();
});

test("el calendario y la búsqueda del mapa siguen disponibles a 360 px", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  await page.goto("/#/");
  await expect(page.locator(".readout")).toContainText("120 mm");
  await expect(page.locator(".map-legend")).toHaveCount(0);

  const slider = page.getByRole("slider", { name: "Temporada, abril a diciembre" });
  expect((await slider.boundingBox())?.width).toBeGreaterThan(260);
  const firstDate = await slider.getAttribute("aria-valuetext");
  await slider.press("ArrowRight");
  await expect(slider).not.toHaveAttribute("aria-valuetext", firstDate!);
  await expect(page.getByText("Calendario provisional", { exact: true })).toBeVisible();

  const handle = page.getByRole("slider", { name: "Alto de la ficha" });
  await handle.press("End");
  await page.getByRole("button", { name: "Comparar años" }).click();
  const years = page.getByRole("dialog", { name: "Comparar años" });
  await expect(years).toBeInViewport();
  await expect(years.getByRole("link", { name: "Ver cifras en Temporada" })).toBeVisible();
  await years.getByRole("button", { name: "Cerrar" }).click();
  await page.getByRole("button", { name: "Ocultar", exact: true }).click();
  await expect(handle).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Lectura", exact: true })).toBeInViewport();

  const search = page.getByRole("textbox", { name: "Buscar cantón" });
  await search.fill("sin resultados 123");
  await expect(page.getByText("No hay cantones que coincidan con la búsqueda.")).toBeVisible();
  await search.fill("San José");
  await page.getByRole("listbox", { name: "Resultados de cantones" }).getByRole("option", { name: /^San José.*sin simulación/ }).click();
  await expect(page.getByRole("search").getByRole("status")).toHaveText("San José: sin simulación disponible.");
  await search.fill("Cañas");
  const results = page.getByRole("listbox", { name: "Resultados de cantones" });
  const canas = results.getByRole("option", { name: "Cañas", exact: true });
  await expect(canas).toBeInViewport();
  await search.press("Enter");
  await expect(canas).toBeFocused();
  await canas.press("Enter");
  await expect(results).toHaveCount(0);
  await expect(page).toHaveURL(/c=canas/);

  await page.getByRole("button", { name: "Capas", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Malla de prueba" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Cerrar" }).click();
  await expect(page.locator(".map-legend")).toBeVisible();
});

const views = [
  ["map", "/#/"],
  ["cantons", "/#/cantones"],
  ["rotations", "/#/rotaciones"],
  ["season", "/#/temporada"],
  ["trust", "/#/confianza"],
] as const;

for (const [name, path] of views) {
  for (const theme of ["night", "sun"] as const) {
    for (const [width, height, size] of [[360, 740, "360"], [768, 1024, "768"], [1440, 900, "desktop"]] as const) {
      test(`captura ${name} ${theme} ${size}`, async ({ page }) => {
        await page.setViewportSize({ width, height });
        await page.goto(path);
        if (theme === "sun") await page.getByRole("button", { name: "Noche" }).click();
        if (name === "rotations") await page.getByRole("region", { name: /Diferencia frente a/ }).waitFor();
        if (name === "season") await page.getByRole("table", { name: "Agua que faltó" }).waitFor();
        if (name === "trust") await page.getByRole("heading", { name: "NASA POWER" }).waitFor();
        if (name === "cantons") await page.getByRole("img", { name: "Límite de Liberia" }).waitFor();
        if (name === "map") await page.getByText("10.55").first().waitFor();
        if (name === "season" || name === "trust" || name === "cantons") {
          const hasOverflow = await page.locator(".screen").evaluate((element) => element.scrollWidth > element.clientWidth + 1);
          expect(hasOverflow).toBe(false);
        }
        await page.waitForTimeout(name === "map" ? 5000 : 300);
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
