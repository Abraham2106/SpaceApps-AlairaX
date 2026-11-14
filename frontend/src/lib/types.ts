export const SCENARIO_IDS = [
  "strong_el_nino",
  "neutral",
  "la_nina",
  "like_2026",
] as const;

export const ROTATION_IDS = ["rice_melon", "rice_legume", "rice_sorghum"] as const;

export const METRIC_IDS = [
  "modeled_water_deficit_mm",
  "crop_water_demand_mm",
  "water_stress_days",
] as const;

export type ScenarioId = (typeof SCENARIO_IDS)[number];
export type RotationId = (typeof ROTATION_IDS)[number];
export type MetricId = (typeof METRIC_IDS)[number];
export type Lang = "es" | "en";
export type ThemeName = "night" | "sun";
export type BasemapId = "satellite" | "modis" | "marble";

export type Zone = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  validated?: boolean;
};

export type Quantiles = {
  p10: number | null;
  p50: number | null;
  p90: number | null;
  n: number;
};

export type MetricSummary = Record<MetricId, Quantiles>;

export type Metrics = {
  crop_water_demand_mm: number | null;
  modeled_water_deficit_mm: number | null;
  water_stress_days: number | null;
};

export type AnalogYear = { year: number; distance: number };

export type DailyBalance = {
  date: string;
  crop_water_demand_mm: number | null;
  modeled_water_deficit_mm: number | null;
  soil_water_storage_mm: number | null;
  water_stress: boolean | null;
};

export type SimulationRun = {
  _mock: boolean;
  generado: string;
  zona: Zone;
  source_refs: string[];
  warnings: string[];
  rotation_id: RotationId;
  scenario_id: ScenarioId;
  year: number;
  environment_id: string;
  metrics: Metrics;
  daily_balance: DailyBalance[];
  assumptions: string[];
  model_version: string;
};

export type RotationComparison = {
  rotation_id: RotationId;
  metrics: MetricSummary;
  delta_vs_baseline: MetricSummary;
  runs: SimulationRun[];
};

export type CompareResponse = {
  schema_version?: string;
  _mock: boolean;
  generado: string;
  zona: Zone;
  source_refs: string[];
  warnings: string[];
  scenario_id: ScenarioId;
  baseline_rotation_id: RotationId;
  analog_years: AnalogYear[];
  rotations: RotationComparison[];
  limitations: string[];
  uncertainty_method: "empirical_linear_quantiles_across_analog_years";
};

export type ScenarioChoice = {
  id: ScenarioId;
  name: string;
  k: number;
  status: "fixture" | "available" | "unavailable" | string;
  reason: string | null;
  sampleWarning: string | null;
  resultFile: string | null;
};

export type Catalog = {
  mock: boolean;
  zona: Zone;
  warnings: string[];
  sourceRefs: string[];
  scenarios: ScenarioChoice[];
  rotations: { id: string; name: string; baseline: boolean }[];
};

export type LoadedComparison = {
  mode: "fixtures" | "live";
  catalog: Catalog;
  compare: CompareResponse | null;
  httpStatus: number | null;
  httpDetail: string | null;
};
