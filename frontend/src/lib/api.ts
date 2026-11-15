import {
  compareResponseSchema,
  fixtureRotationFileSchema,
  fixtureScenarioFileSchema,
  healthSchema,
  liveCatalogSchema,
  liveRotationLibrarySchema,
  sentinelSearchSchema,
  sourcesSchema,
} from "./schemas";
import type { SentinelScene } from "../map/imagery/catalog";
import { translate } from "./i18n";
import type { Catalog, CompareResponse, Lang, LoadedComparison, ScenarioChoice, ScenarioId, Zone } from "./types";
import { SCENARIO_IDS } from "./types";

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

async function fixtureCatalog(signal?: AbortSignal): Promise<Catalog> {
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
        status: "fixture",
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

async function postCompare(base: string, zona: Zone, scenario: ScenarioChoice, signal?: AbortSignal): Promise<CompareResponse> {
  const response = await fetch(`${base}/compare`, {
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
  return compareResponseSchema.parse(body);
}

export async function loadComparison(apiBase: string, scenarioId: ScenarioId, signal?: AbortSignal): Promise<LoadedComparison> {
  if (!apiBase) {
    const catalog = await fixtureCatalog(signal);
    const choice = catalog.scenarios.find((item) => item.id === scenarioId);
    if (!choice?.resultFile) {
      throw new ApiError(404, "El fixture no tiene ese escenario.");
    }
    const body = await readJson(publicUrl(`data/${choice.resultFile}`), signal);
    return {
      mode: "fixtures",
      catalog,
      compare: compareResponseSchema.parse(body),
      httpStatus: 200,
      httpDetail: null,
    };
  }
  const base = apiBase.replace(/\/$/, "");
  const catalog = await liveCatalog(base, signal);
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
    const compare = await postCompare(base, catalog.zona, choice, signal);
    return { mode: "live", catalog, compare, httpStatus: 200, httpDetail: null };
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
