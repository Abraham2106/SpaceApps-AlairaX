import { z } from "zod";
import { METRIC_IDS, ROTATION_IDS, SCENARIO_IDS } from "./types";

const scenarioId = z.enum(SCENARIO_IDS);
const rotationId = z.enum(ROTATION_IDS);

const zone = z
  .object({
    id: z.string(),
    name: z.string(),
    latitude: z.number().gte(-90).lte(90),
    longitude: z.number().gte(-180).lte(180),
    validated: z.boolean().optional(),
  })
  .passthrough();

const quantiles = z
  .object({
    p10: z.number().nullable(),
    p50: z.number().nullable(),
    p90: z.number().nullable(),
    n: z.number().int().nonnegative(),
  })
  .strict();

const metricSummary = z
  .object({
    crop_water_demand_mm: quantiles,
    modeled_water_deficit_mm: quantiles,
    water_stress_days: quantiles,
  })
  .strict();

const metrics = z
  .object({
    crop_water_demand_mm: z.number().nullable(),
    modeled_water_deficit_mm: z.number().nullable(),
    water_stress_days: z.number().int().nonnegative().nullable(),
  })
  .strict();

const daily = z
  .object({
    date: z.string(),
    crop_water_demand_mm: z.number().nullable(),
    modeled_water_deficit_mm: z.number().nullable(),
    soil_water_storage_mm: z.number().nullable(),
    water_stress: z.boolean().nullable(),
  })
  .strict();

const run = z
  .object({
    schema_version: z.string().optional(),
    _mock: z.boolean(),
    generado: z.string(),
    zona: zone,
    source_refs: z.array(z.string()),
    warnings: z.array(z.string()),
    rotation_id: rotationId,
    scenario_id: scenarioId,
    year: z.number().int(),
    environment_id: z.string(),
    metrics,
    daily_balance: z.array(daily),
    assumptions: z.array(z.string()),
    model_version: z.string().min(1),
  })
  .passthrough();

export const compareResponseSchema = z
  .object({
    schema_version: z.string().optional(),
    _mock: z.boolean(),
    generado: z.string(),
    zona: zone,
    source_refs: z.array(z.string()),
    warnings: z.array(z.string()),
    scenario_id: scenarioId,
    baseline_rotation_id: rotationId,
    analog_years: z.array(
      z.object({ year: z.number().int(), distance: z.number().nonnegative() }).strict(),
    ),
    rotations: z.array(
      z
        .object({
          rotation_id: rotationId,
          metrics: metricSummary,
          delta_vs_baseline: metricSummary,
          runs: z.array(run),
        })
        .strict(),
    ),
    limitations: z.array(z.string()),
    uncertainty_method: z.literal("empirical_linear_quantiles_across_analog_years"),
  })
  .passthrough();

export const fixtureScenarioFileSchema = z
  .object({
    _mock: z.boolean(),
    zona: zone,
    warnings: z.array(z.string()).optional(),
    source_refs: z.array(z.string()).optional(),
    scenarios: z.array(
      z.object({
        scenario_id: scenarioId,
        name: z.string(),
        result_file: z.string().regex(/^compare-[a-z0-9_]+\.json$/),
        selection_status: z.string(),
        k: z.number().int().positive(),
        sample_warning: z.string().nullable(),
      }),
    ),
  })
  .passthrough();

export const fixtureRotationFileSchema = z
  .object({
    _mock: z.boolean(),
    rotations: z.array(
      z.object({
        rotation_id: z.string(),
        name: z.string(),
        baseline: z.boolean(),
      }),
    ),
  })
  .passthrough();

export const liveCatalogSchema = z
  .object({
    _mock: z.boolean(),
    zona: zone,
    warnings: z.array(z.string()).optional(),
    source_refs: z.array(z.string()).optional(),
    scenarios: z.record(
      z.string(),
      z
        .object({
          status: z.string(),
          reason: z.string().nullable().optional(),
          k: z.number().int().positive(),
        })
        .passthrough(),
    ),
  })
  .passthrough();

export const liveRotationLibrarySchema = z
  .object({
    rotations: z.array(
      z.object({
        rotation_id: z.string(),
        name: z.string(),
        is_current: z.boolean().optional(),
      }),
    ),
  })
  .passthrough();

export const healthSchema = z
  .object({
    status: z.string(),
    model_version: z.string().optional(),
  })
  .passthrough();

export const sourcesSchema = z
  .object({
    _mock: z.boolean(),
    source_refs: z.array(z.string()),
  })
  .passthrough();

const isoDay = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);

/** Respuesta de GET /imagery/search. La escena es null cuando no hay una despejada. */
export const sentinelSearchSchema = z
  .object({
    provider: z.string(),
    resolution_m: z.number(),
    requested_date: isoDay,
    scene: z
      .object({
        id: z.string().regex(/^S2[A-D]_\d{2}[A-Z]{3}_\d{8}_\d+_L2A$/),
        date: isoDay,
        datetime: z.string(),
        cloud_cover: z.number().nullable(),
        platform: z.string().nullable(),
        bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]),
      })
      .passthrough()
      .nullable(),
    reason: z.string().nullable(),
    attribution: z.string().nullable(),
  })
  .passthrough();

export const metricIdSchema = z.enum(METRIC_IDS);
