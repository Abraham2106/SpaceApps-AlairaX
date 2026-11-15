import { translate } from "./i18n";
import type { Lang, MetricId } from "./types";

export function formatNumber(value: number, lang: Lang, digits = 1): string {
  return new Intl.NumberFormat(lang === "es" ? "es-CR" : "en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: Number.isInteger(value) ? 0 : Math.min(digits, 1),
  }).format(value);
}

export function formatValue(value: number | null, metric: MetricId, lang: Lang): string {
  if (value === null) return "";
  return `${formatNumber(value, lang)} ${metricUnit(metric, lang)}`;
}

export function formatSigned(value: number | null, metric: MetricId, lang: Lang): string {
  if (value === null) return "";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  const body = formatNumber(Math.abs(value), lang, 1);
  return `${sign}${body} ${metricUnit(metric, lang)}`;
}

export function metricUnit(metric: MetricId, lang: Lang): string {
  return metric === "water_stress_days" ? translate(lang, "format.days") : "mm";
}
