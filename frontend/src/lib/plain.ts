import { formatSigned, formatValue } from "./format";
import type { Lang, MetricId, RotationId } from "./types";

export const ROTATION_ORDER: RotationId[] = ["rice_melon", "rice_legume", "rice_sorghum"];

export const ROTATION_STYLE: Record<
  RotationId,
  { color: string; dash: string; swatch: string }
> = {
  // El color es una variable de index.css (--rot-*): cambia con el tema. El trazo no.
  rice_melon: { color: "var(--rot-melon)", dash: "none", swatch: "solid" },
  rice_legume: { color: "var(--rot-legume)", dash: "7 4", swatch: "dashed" },
  rice_sorghum: { color: "var(--rot-sorghum)", dash: "1.5 4", swatch: "dotted" },
};

const FALLBACK_NAME: Record<RotationId, { es: string; en: string }> = {
  rice_melon: { es: "Arroz → melón", en: "Rice → melon" },
  rice_legume: { es: "Arroz → leguminosa", en: "Rice → legume" },
  rice_sorghum: { es: "Arroz → sorgo", en: "Rice → sorghum" },
};

export function rotationName(id: string, lang: Lang, fromData?: string): string {
  if (fromData && lang === "es") return fromData;
  if (id in FALLBACK_NAME) return FALLBACK_NAME[id as RotationId][lang];
  return fromData ?? id;
}

const METRIC_NOUN: Record<MetricId, { es: string; en: string }> = {
  modeled_water_deficit_mm: {
    es: "déficit hídrico modelado",
    en: "modeled water deficit",
  },
  crop_water_demand_mm: {
    es: "demanda hídrica modelada",
    en: "modeled crop water demand",
  },
  water_stress_days: {
    es: "días de estrés modelados",
    en: "modeled stress days",
  },
};

export function metricNoun(metric: MetricId, lang: Lang): string {
  return METRIC_NOUN[metric][lang];
}

export type SentenceInput = {
  lang: Lang;
  scenarioName: string;
  metric: MetricId;
  rotationName: string;
  baselineName: string;
  isBaseline: boolean;
  p50: number | null;
  deltaP50: number | null;
  n: number;
  like2026: boolean;
};

/**
 * Plain language from the contract numbers only.
 * The negation is required: these words are the claim the screen must not make.
 */
export function comparisonSentence(input: SentenceInput): string {
  const { lang, scenarioName, metric, rotationName: name, baselineName, isBaseline, p50, deltaP50, n, like2026 } = input;
  const noun = metricNoun(metric, lang);
  const watch =
    lang === "es"
      ? "No es rendimiento, ni ahorro, ni una rotación ganadora."
      : "This is not yield, not savings, and not a winning rotation.";
  const sample =
    lang === "es"
      ? `La muestra tiene ${n} ${n === 1 ? "año análogo" : "años análogos"}. p10–p90 es la variación entre esos años, no una probabilidad ni un intervalo de confianza.`
      : `The sample has ${n} analog ${n === 1 ? "year" : "years"}. p10–p90 is the spread across those years, not a probability and not a confidence interval.`;
  const follow =
    like2026
      ? lang === "es"
        ? " 2026 no entra como análogo: el escenario solo pide años parecidos y 2026 queda en seguimiento."
        : " 2026 is not an analog year: the scenario only asks for similar years, and 2026 stays in monitoring."
      : "";

  if (p50 === null || (deltaP50 === null && !isBaseline)) {
    return lang === "es"
      ? `${name}: sin dato para ${noun}. El contrato no trajo el número. No se muestra como cero. ${sample}`
      : `${name}: no data for ${noun}. The contract did not include the number. It is not shown as zero. ${sample}`;
  }

  if (isBaseline) {
    return lang === "es"
      ? `${name} es la referencia en ${scenarioName}. La mediana modelada de ${noun} es ${formatValue(p50, metric, lang)}. El delta es 0 porque la resta es contra ella misma, no porque el campo esté en equilibrio.${follow} ${sample} ${watch}`
      : `${name} is the reference in ${scenarioName}. The modeled median ${noun} is ${formatValue(p50, metric, lang)}. The delta is 0 because it is subtracted from itself, not because the field is in balance.${follow} ${sample} ${watch}`;
  }

  const direction =
    deltaP50 === null
      ? ""
      : deltaP50 === 0
        ? lang === "es"
          ? `La mediana del delta contra ${baselineName} es 0.`
          : `The median delta against ${baselineName} is 0.`
        : deltaP50 < 0
          ? lang === "es"
            ? `La mediana queda ${formatSigned(deltaP50, metric, lang)} respecto de ${baselineName}: un valor modelado más bajo.`
            : `The median sits ${formatSigned(deltaP50, metric, lang)} against ${baselineName}: a lower modeled value.`
          : lang === "es"
            ? `La mediana queda ${formatSigned(deltaP50, metric, lang)} respecto de ${baselineName}: un valor modelado más alto.`
            : `The median sits ${formatSigned(deltaP50, metric, lang)} against ${baselineName}: a higher modeled value.`;

  return lang === "es"
    ? `${name}, en ${scenarioName}: la mediana de ${noun} es ${formatValue(p50, metric, lang)}. ${direction} El delta ya viene calculado año por año, antes de los cuantiles.${follow} ${sample} ${watch}`
    : `${name}, in ${scenarioName}: the median ${noun} is ${formatValue(p50, metric, lang)}. ${direction} The delta was computed year by year before the quantiles.${follow} ${sample} ${watch}`;
}

export function farmerLine(input: SentenceInput): string {
  const { lang, rotationName: name, metric, isBaseline, p50, deltaP50, n } = input;
  const years = lang === "es" ? `${n} años parecidos` : `${n} similar years`;
  if (p50 === null || (deltaP50 === null && !isBaseline)) {
    return lang === "es" ? `${name}: sin dato. ${years}.` : `${name}: no data. ${years}.`;
  }
  if (isBaseline) {
    return lang === "es"
      ? `${name}: ${formatValue(p50, metric, lang)} en el ciclo. Es la rotación con la que se comparan las otras. ${years}.`
      : `${name}: ${formatValue(p50, metric, lang)} in the cycle. The other rotations are compared with this one. ${years}.`;
  }
  const delta = deltaP50 ?? 0;
  const amount = formatValue(Math.abs(delta), metric, lang);
  if (lang === "es") {
    const sense = delta < 0 ? `${amount} menos` : delta > 0 ? `${amount} más` : "lo mismo";
    return `${name}: ${formatValue(p50, metric, lang)}. ${sense} que arroz → melón. ${years}.`;
  }
  const sense = delta < 0 ? `${amount} less` : delta > 0 ? `${amount} more` : "the same";
  return `${name}: ${formatValue(p50, metric, lang)}. ${sense} than rice → melon. ${years}.`;
}

export function compactLine(input: SentenceInput): string {
  const { lang, rotationName: name, metric, isBaseline, p50, deltaP50, n } = input;
  if (p50 === null || (deltaP50 === null && !isBaseline)) {
    return lang === "es" ? `${name}: sin dato · n = ${n}` : `${name}: no data · n = ${n}`;
  }
  if (isBaseline) {
    return lang === "es"
      ? `${name}: ${formatValue(p50, metric, lang)} · referencia · n = ${n}`
      : `${name}: ${formatValue(p50, metric, lang)} · reference · n = ${n}`;
  }
  return lang === "es"
    ? `${name}: ${formatValue(p50, metric, lang)} · delta ${formatSigned(deltaP50, metric, lang)} · n = ${n}`
    : `${name}: ${formatValue(p50, metric, lang)} · delta ${formatSigned(deltaP50, metric, lang)} · n = ${n}`;
}

export function leadSentence(lang: Lang, scenarioName: string, metric: MetricId, n: number, mock: boolean): string {
  const noun = metricNoun(metric, lang);
  if (lang === "es") {
    const source = mock
      ? "Los números salen de un fixture sintético, no de una corrida de campo."
      : "Los números salen de la respuesta que entregó la API.";
    return `En ${scenarioName} hay ${n} años en la muestra. Estas son las medianas de ${noun}. ${source}`;
  }
  const source = mock
    ? "The numbers come from a synthetic fixture, not a field run."
    : "The numbers come from the API response.";
  return `In ${scenarioName} the sample has ${n} years. These are the medians of ${noun}. ${source}`;
}
