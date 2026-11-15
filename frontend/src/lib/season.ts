import type { CompareResponse } from "./types";

export const SEASON_MONTHS = [
  [0, "month.april"],
  [30, "month.may"],
  [61, "month.june"],
  [91, "month.july"],
  [122, "month.august"],
  [153, "month.september"],
  [183, "month.october"],
  [214, "month.november"],
  [244, "month.december"],
] as const;

export function comparisonYears(compare: CompareResponse | null | undefined): number[] {
  return compare?.analog_years.map(({ year }) => year).filter((year) => year !== 2026) ?? [];
}

export function hasDailyBalance(compare: CompareResponse | null | undefined): boolean {
  return compare?.rotations.some((rotation) => rotation.runs.some((run) => run.daily_balance.length > 0)) ?? false;
}

export function seasonDates(compare: CompareResponse | null | undefined, year: number | null): string[] {
  const runs = compare?.rotations.find(({ rotation_id }) => rotation_id === compare.baseline_rotation_id)?.runs ?? [];
  const run = runs.find((item) => item.year === year) ?? runs[0];
  return run?.daily_balance.map(({ date }) => date) ?? [];
}
