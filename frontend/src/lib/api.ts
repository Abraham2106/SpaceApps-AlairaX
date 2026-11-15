import {
  compareResponseSchema,
  fixtureRotationFileSchema,
  fixtureScenarioFileSchema,
  healthSchema,
  liveCatalogSchema,
  liveRotationLibrarySchema,
  sentinelSearchSchema,
  droneSearchSchema,
  sourcesSchema,
} from "./schemas";
import type { DroneImage, SentinelScene } from "../map/imagery/catalog";
import { translate } from "./i18n";
import type { Catalog, CompareResponse, Lang, LoadedComparison, ScenarioChoice, ScenarioId, Zone } from "./types";
import { SCENARIO_IDS } from "./types";
import { z } from "zod";

const cantonCatalogSchema = z.object({
  cantons: z.record(z.string(), z.object({
    name: z.string(),
    latitude: z.number().gte(-90).lte(90),
    longitude: z.number().gte(-180).lte(180),
  })),
});

export class ApiError extends Error {
  status: number;
  detail: string | null;

  constructor(status: number, detail: string | null) {
    super(detail ?? `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

function isScenarioId(value: string): value is ScenarioId {
  return (SCENARIO_IDS as readonly string[]).includes(value);
}

async function readJson(url: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new ApiError(response.status, `${response.status} ${url}`);
  }
  return response.json();
}

function detailOf(body: unknown): string | null {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail || null;
    if (detail != null) return JSON.stringify(detail);
  }
  return null;
}

export function comparisonError(loaded: LoadedComparison | undefined, lang: Lang): string | null {
  return loaded?.httpDetail ?? (loaded?.httpDetailKey ? translate(lang, loaded.httpDetailKey) : null);
}

export function publicUrl(path: string): string {
  const base = import.meta.env.BASE_URL ?? "/";
  return `${base}${path.replace(/^\//, "")}`;
}

async function staticCatalog(signal?: AbortSignal): Promise<Catalog> {
  const [scenarioFile, rotationFile] = await Promise.all([
    readJson(publicUrl("data/scenarios.json"), signal),
    readJson(publicUrl("data/rotations.json"), signal),
  ]);
  const scenarios = fixtureScenarioFileSchema.parse(scenarioFile);
  const rotations = fixtureRotationFileSchema.parse(rotationFile);
  return {
    mock: scenarios._mock || rotations._mock,
    zona: scenarios.zona,
    warnings: scenarios.warnings ?? [],
    sourceRefs: scenarios.source_refs ?? [],
    scenarios: scenarios.scenarios.map(
      (item): ScenarioChoice => ({
        id: item.scenario_id,
        name: item.name,
        k: item.k,
        status: scenarios._mock ? "fixture" : item.selection_status,
        reason: null,
        sampleWarning: item.sample_warning,
        resultFile: item.result_file,
      }),
    ),
    rotations: rotations.rotations.map((item) => ({
      id: item.rotation_id,
      name: item.name,
      baseline: item.baseline,
    })),
  };
}

async function liveCatalog(base: string, signal?: AbortSignal): Promise<Catalog> {
  const [scenarioBody, rotationBody, sourceBody] = await Promise.all([
    readJson(`${base}/scenarios`, signal),
    readJson(`${base}/rotations`, signal).catch(() => null),
    readJson(`${base}/sources`, signal).catch(() => null),
  ]);
  const scenarios = liveCatalogSchema.parse(scenarioBody);
  const choices: ScenarioChoice[] = [];
  for (const [id, item] of Object.entries(scenarios.scenarios)) {
    if (!isScenarioId(id)) continue;
    choices.push({
      id,
      name: translate("es", `scenario.${id}`),
      k: item.k,
      status: item.status,
      reason: item.reason ?? null,
      sampleWarning: null,
      resultFile: null,
    });
  }
  const rotations = rotationBody
    ? liveRotationLibrarySchema.parse(rotationBody).rotations.map((item) => ({
        id: item.rotation_id,
        name: item.name,
        baseline: Boolean(item.is_current),
      }))
    : [];
  const sources = sourceBody ? sourcesSchema.safeParse(sourceBody) : null;
  return {
    mock: scenarios._mock,
    zona: scenarios.zona,
    warnings: scenarios.warnings ?? [],
    sourceRefs: sources?.success ? sources.data.source_refs : (scenarios.source_refs ?? []),
    scenarios: choices,
    rotations,
  };
}

export async function probeHealth(base: string, signal?: AbortSignal): Promise<boolean> {
  try {
    const body = await readJson(`${base.replace(/\/$/, "")}/health`, signal);
    return healthSchema.safeParse(body).success;
  } catch {
    return false;
  }
}

/**
 * Pide al backend la escena Sentinel-2 L2A menos nublada de los 15 días previos a `date`
 * que cubre el punto. Devuelve null si no hay ninguna con nubosidad aceptable.
 */
export async function findSentinelScene(
  base: string,
  query: { date: string; lon: number; lat: number },
  signal?: AbortSignal,
): Promise<SentinelScene | null> {
  const params = new URLSearchParams({
    date: query.date,
    lon: query.lon.toFixed(4),
    lat: query.lat.toFixed(4),
  });
  const body = sentinelSearchSchema.parse(await readJson(`${base.replace(/\/$/, "")}/imagery/search?${params}`, signal));
  if (!body.scene || !body.attribution) return null;
  return {
    id: body.scene.id,
    date: body.scene.date,
    datetime: body.scene.datetime,
    cloudCover: body.scene.cloud_cover,
    platform: body.scene.platform,
    bbox: body.scene.bbox,
    attribution: body.attribution,
  };
}

async function postCompare(base: string, zona: Zone, scenario: ScenarioChoice, signal?: AbortSignal, cantonId?: string): Promise<CompareResponse> {
  const path = cantonId ? `/cantons/${encodeURIComponent(cantonId)}/compare` : "/compare";
  const response = await fetch(`${base}${path}`, {
    method: "POST",
    signal,
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      zona,
      scenario_id: scenario.id,
      baseline_rotation_id: "rice_melon",
      rotation_ids: ["rice_melon", "rice_legume", "rice_sorghum"],
      k: scenario.k,
    }),
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, detailOf(body));
  const compare = compareResponseSchema.parse(body);
  if (cantonId && (compare.zona.id !== cantonId || compare.zona.latitude !== zona.latitude || compare.zona.longitude !== zona.longitude)) {
    throw new ApiError(502, "La simulación recibida no corresponde al cantón seleccionado.");
  }
  return compare;
}

async function loadStaticComparison(scenarioId: ScenarioId, signal?: AbortSignal, cantonId?: string): Promise<LoadedComparison> {
  const catalog = await staticCatalog(signal);
  const choice = catalog.scenarios.find((item) => item.id === scenarioId);
  if (!choice?.resultFile) {
    throw new ApiError(404, "El catálogo no tiene ese escenario.");
  }
  const path = cantonId
    ? `data/cantons/${encodeURIComponent(cantonId)}/compare-${scenarioId}.json`
    : `data/${choice.resultFile}`;
  const compare = compareResponseSchema.parse(await readJson(publicUrl(path), signal));
  if (cantonId && compare.zona.id !== cantonId) {
    throw new ApiError(502, "El archivo de simulación no corresponde al cantón seleccionado.");
  }
  return {
    mode: "static",
    catalog: cantonId ? comparisonCatalog(catalog, compare) : catalog,
    compare,
    httpStatus: 200,
    httpDetail: null,
  };
}

function comparisonCatalog(catalog: Catalog, compare: CompareResponse): Catalog {
  return { ...catalog, zona: compare.zona, warnings: compare.warnings, sourceRefs: compare.source_refs };
}

async function loadLiveComparison(base: string, scenarioId: ScenarioId, signal?: AbortSignal, cantonId?: string): Promise<LoadedComparison> {
  const [regionalCatalog, cantonDocument] = await Promise.all([
    liveCatalog(base, signal),
    cantonId ? readJson(`${base}/chat/cantons`, signal) : Promise.resolve(null),
  ]);
  let catalog = regionalCatalog;
  if (cantonId) {
    const point = cantonCatalogSchema.parse(cantonDocument).cantons[cantonId];
    if (!point) throw new ApiError(404, "El cantón seleccionado no pertenece al piloto de Guanacaste.");
    catalog = { ...catalog, zona: { id: cantonId, ...point, validated: false } };
  }
  const choice = catalog.scenarios.find((item) => item.id === scenarioId);
  if (!choice) {
    return {
      mode: "live",
      catalog,
      compare: null,
      httpStatus: 404,
      httpDetail: null,
      httpDetailKey: "api.scenarioMissing",
    };
  }
  try {
    const compare = await postCompare(base, catalog.zona, choice, signal, cantonId);
    return { mode: "live", catalog: cantonId ? comparisonCatalog(catalog, compare) : catalog, compare, httpStatus: 200, httpDetail: null };
  } catch (error) {
    if (error instanceof ApiError) {
      return {
        mode: "live",
        catalog,
        compare: null,
        httpStatus: error.status,
        httpDetail: error.detail,
        httpDetailKey: error.detail ? undefined : "api.noErrorDetail",
      };
    }
    throw error;
  }
}

/**
 * Pide al backend las huellas de dron de OpenAerialMap que tocan la caja
 * [oeste, sur, este, norte]. El navegador no puede pedirlas directo: OAM no abre CORS.
 */
export async function findDroneImages(
  base: string,
  box: readonly [number, number, number, number],
  signal?: AbortSignal,
): Promise<DroneImage[]> {
  const [west, south, east, north] = box;
  const params = new URLSearchParams({ west: String(west), south: String(south), east: String(east), north: String(north) });
  const body = droneSearchSchema.parse(await readJson(`${base.replace(/\/$/, "")}/imagery/drones?${params}`, signal));
  return body.images.map((image) => ({
    id: image.id,
    title: image.title,
    date: image.date,
    gsdM: image.gsd_m,
    provider: image.provider,
    license: image.license || body.license,
    bbox: image.bbox,
    tiles: image.tiles,
  }));
}

export async function loadComparison(apiBase: string, scenarioId: ScenarioId, signal?: AbortSignal, cantonId?: string): Promise<LoadedComparison> {
  return apiBase
    ? loadLiveComparison(apiBase.replace(/\/$/, ""), scenarioId, signal, cantonId)
    : loadStaticComparison(scenarioId, signal, cantonId);
}
