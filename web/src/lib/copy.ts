// Window-parametrised copy (Stage 3 T11, B6). Every sentence that names the evaluation period, or
// states a reading that was made on the validation year, comes from here, so no validation wording
// ever sits next to a test-year number. The test copy reads its dates from the test manifest.
import type { Json } from './data';
import { fmtDate, pctRange } from './format';

export type EvalWindow = 'validation' | 'test';

/** The one plain-language line about the validation year (A6). */
export const VALIDATION_LINE = 'These are validation-year results, which shaped the design; the sealed test year is the real test.';
/** Its test-year counterpart. */
export const TEST_LINE = 'These are sealed test-year results: the year was opened once, after the model and policy settings were frozen, and nothing was tuned on it.';
/** Validation chip, kept verbatim from Task 8 (the offline test reads it). */
export const SEALED = 'Validation year (Nov 2024 – Oct 2025) · test year sealed, opened once';

export interface WindowCopy {
  window: EvalWindow;
  /** the top bar's status line for this window */
  chip: string;
  footShort: string;
  footLong: string;
  /** "Over the validation year" / "Over the test year": a sentence opener for headline numbers */
  over: string;
  /** the cockpit's registered-result lead */
  resultLead: string;
  /** the plain line about what kind of evidence this is */
  line: string;
  lineTestId: string;
  cohortTitle: string;
  /** label for the forecast errors over the whole scored period */
  periodMae: string;
  /** readings that were made on the validation year: shown only there */
  validationReadings: boolean;
  /** M14: the period a number covers. Test copy never says "all year" or "over the year". */
  overYear: string; // "over the year" | "over the covered period (N weeks)"
  allYear: string; // "all year" | "over the covered period (N weeks)"
  yearPoss: string; // "the year's" | "the covered period's"
  yearMean: string; // "year mean" | "period mean"
  yearShort: string; // "year" | "period"
  wholeYear: string; // "the whole year" | "the whole covered period"
}

/** "Over the year" from "over the year". */
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

const span = (a: string, b: string) => `${fmtDate(a, { month: 'short', year: 'numeric', timeZone: 'UTC' })} – ${fmtDate(new Date(new Date(b).getTime() - 1).toISOString(), { month: 'short', year: 'numeric', timeZone: 'UTC' })}`;

/** The freeze date from a test manifest, e.g. "Oct 27, 2026"; null when there is none. */
export function freezeDate(man: Json | null | undefined): string | null {
  const t: string | undefined = man?.freeze?.wallclock_frozen_at;
  // the dashboard keeps Mountain time (America/Denver, fmtDate's default), as its hours do (r1 m9)
  return t ? fmtDate(t, { month: 'short', day: 'numeric', year: 'numeric' }) : null;
}

/** The switch's label for the test option: "Test year (sealed until <freeze>)". `frozenAt` is the
 * freeze time copy-data reads from results/test/manifest.json; null before the test run exists. */
export const testOptionLabel = (frozenAt: string | null | undefined, available = false) =>
  available ? 'Test year (sealed, opened once)' : `Test year (sealed until ${frozenAt ? fmtDate(frozenAt, { month: 'short', day: 'numeric', timeZone: 'UTC' }) : 'the freeze'})`;

export function windowCopy(window: EvalWindow, man: Json, metrics?: Json): WindowCopy {
  if (window === 'validation') {
    return {
      overYear: 'over the year', allYear: 'all year', yearPoss: "the year's", yearMean: 'year mean',
      yearShort: 'year', wholeYear: 'the whole year',
      window,
      chip: SEALED,
      footShort: 'Hours in America/Denver time. Validation year data.',
      footLong: 'EIA-930 hourly balance and EIA consumption-basis CO₂, validation year (Nov 2024 – Oct 2025).',
      over: 'Over the validation year',
      resultLead: 'Registered result, the whole validation year',
      line: VALIDATION_LINE,
      lineTestId: 'validation-line',
      cohortTitle: 'Every policy, the validation cohort',
      periodMae: 'Over the selection period',
      validationReadings: true,
    };
  }
  const covered = span(man.split.eval_start, man.split.F);
  const fz = freezeDate(man);
  const nw: number | undefined = metrics?.cohort?.n_weeks?.value;
  const period = `over the covered period${nw ? ` (${nw} weeks)` : ''}`;
  return {
    overYear: period, allYear: period, yearPoss: "the covered period's", yearMean: 'period mean',
    yearShort: 'period', wholeYear: 'the whole covered period',
    window,
    chip: `Test year (${covered}) · opened once, after the freeze${fz ? ` of ${fz}` : ''}`,
    footShort: 'Hours in America/Denver time. Test year data.',
    footLong: `EIA-930 hourly balance and EIA consumption-basis CO₂, test year (${covered}, to the snapshot's last complete day).`,
    over: 'Over the test year',
    resultLead: `Test-year result, ${covered}`,
    line: TEST_LINE,
    lineTestId: 'test-line',
    cohortTitle: 'Every policy, the test cohort',
    periodMae: 'Over the test year',
    validationReadings: false,
  };
}

/** The control room's headline. Validation keeps its registered wording; the test year's is built from
 * its own numbers, so a reading made on the validation year is never put on test numbers. */
export function heroHeadline(c: WindowCopy, h: { placement: { lo: number; hi: number }; timing: { lo: number; hi: number } }, s?: { v: number }): string {
  // F06/F10 (T15): lead with S's own estimate, "about 22.5%" against "under 1%"; never a span across policies
  const tUnder = h.timing.lo >= 0 && h.timing.hi < 0.01;
  if (c.validationReadings && s) return `In a simulated replay, moving Utah's AI jobs cut their attributed CO₂ by about ${Math.round(s.v * 200) / 2}%; waiting in Utah cut ${tUnder ? 'under 1%' : `${pctRange(h.timing.lo, h.timing.hi)}%`}.`;
  if (c.validationReadings) return "In a simulated replay, moving Utah's AI jobs cut their CO₂ by a fifth. Waiting barely helps.";
  if (s) h = { ...h, placement: { lo: s.v, hi: s.v } };
  const verb = (lo: number, hi: number, it: string) =>
    lo > 0 ? `cut ${it} by ${pctRange(lo, hi)}%`
      : hi < 0 ? `raised ${it} by ${pctRange(-hi, -lo)}%`
        : `left ${it} within ${pctRange(Math.max(-lo, hi), Math.max(-lo, hi))}%`;
  return `Sealed test year, simulated replay: moving Utah's AI jobs ${verb(h.placement.lo, h.placement.hi, 'their CO₂')}; waiting in Utah alone ${verb(h.timing.lo, h.timing.hi, 'it')}.`;
}
