import type { Lang, MetricId } from "./types";

const UNITS: Record<MetricId, { es: string; en: string }> = {
  modeled_water_deficit_mm: { es: "mm", en: "mm" },
  crop_water_demand_mm: { es: "mm", en: "mm" },
  water_stress_days: { es: "días", en: "days" },
};

export function formatNumber(value: number, lang: Lang, digits = 1): string {
  return new Intl.NumberFormat(lang === "es" ? "es-CR" : "en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: Number.isInteger(value) ? 0 : Math.min(digits, 1),
  }).format(value);
}

export function formatValue(value: number | null, metric: MetricId, lang: Lang): string {
  if (value === null) return lang === "es" ? "sin dato" : "no data";
  const digits = metric === "water_stress_days" ? 1 : 1;
  return `${formatNumber(value, lang, digits)} ${UNITS[metric][lang]}`;
}

export function formatSigned(value: number | null, metric: MetricId, lang: Lang): string {
  if (value === null) return lang === "es" ? "sin dato" : "no data";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  const body = formatNumber(Math.abs(value), lang, 1);
  return `${sign}${body} ${UNITS[metric][lang]}`;
}

export function metricUnit(metric: MetricId, lang: Lang): string {
  return UNITS[metric][lang];
}
