import { translate } from "./i18n";
import { formatSigned, formatValue } from "./format";
import type { Lang, MetricId, RotationId } from "./types";

export const ROTATION_ORDER: RotationId[] = ["rice_melon", "rice_legume", "rice_sorghum"];

export const ROTATION_STYLE: Record<
  RotationId,
  { color: string; dash: string; swatch: "solid" | "dashed" | "dotted" }
> = {
  // El color es una variable de index.css (--rot-*): cambia con el tema. El trazo no.
  rice_melon: { color: "var(--rot-melon)", dash: "none", swatch: "solid" },
  rice_legume: { color: "var(--rot-legume)", dash: "7 4", swatch: "dashed" },
  rice_sorghum: { color: "var(--rot-sorghum)", dash: "1.5 4", swatch: "dotted" },
};

export function rotationName(id: string, lang: Lang, fromData?: string): string {
  if (fromData && lang === "es") return fromData;
  const known = ROTATION_ORDER.find((rotation) => rotation === id);
  return known ? translate(lang, `rotation.${known}`) : fromData ?? id;
}

export function metricNoun(metric: MetricId, lang: Lang): string {
  return translate(lang, `metric.${metric}.noun`);
}

export function readingMetric(metric: MetricId, lang: Lang): string {
  return translate(lang, `metric.${metric}.reading`);
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
  const watch = translate(lang, "plain.thisNotYieldNotSavings");
  const sample = [
    translate(lang, n === 1 ? "plain.oneAnalogYear" : "plain.analogYears", { count: n }),
    translate(lang, "plain.quantileSpread"),
  ].join(" ");
  const follow =
    like2026
      ? translate(lang, "plain.2026NotAnalogYearScenario")
      : "";

  if (p50 === null || (deltaP50 === null && !isBaseline)) {
    return translate(lang, "plain.noDataContractDidNot", { name, noun, sample });
  }

  if (isBaseline) {
    return translate(lang, "plain.referenceModeledMedianDelta0", { name, scenarioName, noun, value: formatValue(p50, metric, lang), follow, sample, watch });
  }

  const direction =
    deltaP50 === null
      ? ""
      : deltaP50 === 0
        ? translate(lang, "plain.medianDeltaAgainst0", { baselineName })
        : deltaP50 < 0
          ? translate(lang, "plain.medianSitsAgainstLowerModeled", { difference: formatSigned(deltaP50, metric, lang), baselineName })
          : translate(lang, "plain.medianSitsAgainstHigherModeled", { difference: formatSigned(deltaP50, metric, lang), baselineName });

  return translate(lang, "plain.medianDeltaWasComputedYear", { name, scenarioName, noun, value: formatValue(p50, metric, lang), direction, follow, sample, watch });
}

export function farmerLine(input: SentenceInput): string {
  const { lang, rotationName: name, metric, isBaseline, p50, deltaP50, n } = input;
  const years = translate(lang, "plain.similarYears", { count: n });
  if (p50 === null || (deltaP50 === null && !isBaseline)) {
    return translate(lang, "plain.noData", { name, years });
  }
  if (isBaseline) {
    return translate(lang, "plain.cycleOtherRotationsAreCompared", { name, value: formatValue(p50, metric, lang), years });
  }
  const delta = deltaP50 ?? 0;
  const amount = formatValue(Math.abs(delta), metric, lang);
  const sense = delta === 0
    ? translate(lang, "plain.farmerEqual")
    : translate(lang, delta < 0 ? "plain.farmerLower" : "plain.farmerHigher", { amount });
  return translate(lang, "plain.farmerDifference", { name, value: formatValue(p50, metric, lang), sense, years });
}

export function compactLine(input: SentenceInput): string {
  const { lang, rotationName: name, metric, isBaseline, p50, deltaP50, n } = input;
  if (p50 === null || (deltaP50 === null && !isBaseline)) {
    return translate(lang, "plain.noDataN", { name, count: n });
  }
  if (isBaseline) {
    return translate(lang, "plain.referenceN", { name, value: formatValue(p50, metric, lang), count: n });
  }
  return translate(lang, "plain.deltaN", { name, value: formatValue(p50, metric, lang), difference: formatSigned(deltaP50, metric, lang), count: n });
}

export function leadSentence(lang: Lang, scenarioName: string, metric: MetricId, n: number, mock: boolean): string {
  return translate(lang, "plain.readingLead", {
    scenarioName,
    count: n,
    noun: metricNoun(metric, lang),
    source: translate(lang, mock ? "plain.mockSource" : "plain.apiSource"),
  });
}

export function readingNotes(lang: Lang, like2026: boolean): string {
  const caveats = translate(lang, "plain.readingCaveats");
  return like2026 ? `${caveats} ${translate(lang, "plain.followUp2026")}` : caveats;
}
