import { create } from 'zustand';
import type { EvalWindow } from './copy';
import type { Dest, Results, ResultsIndex } from './data';

/** The Story page's views (the existing dashboard); each is a hash route of its own (#control, #story-3, ...). */
export type View = 'control' | 'cockpit' | 'ribbon' | 'story';
/** The nav shell's pages (T21). Story is the dashboard and the default; the others are standalone pages. */
export type Page = 'story' | 'monitor' | 'outlook' | 'regions' | 'prices' | 'evidence';
export const PAGES: { id: Page; label: string }[] = [
  { id: 'story', label: 'Story' },
  { id: 'monitor', label: 'Monitor' },
  { id: 'outlook', label: 'Outlook' },
  { id: 'regions', label: 'Regions' },
  { id: 'prices', label: 'Prices' },
  { id: 'evidence', label: 'Evidence' },
];
/** Pages the evaluation-window switch applies to: they read results/ or results/test/ by the switch. */
export const WINDOWED: Page[] = ['story', 'evidence'];
export type Mode = 'now' | 'wait' | 'move';
/** The control-room toggle (T15, D-064): which already-computed validation scenario the map, rows and hero show. */
export type ScenarioId = 'registered' | 'mobility_le_8gpus' | 'dest_slots_0' | 'dest_slots_1024';
export const VIEWS: { id: View; label: string }[] = [
  { id: 'control', label: 'Control room' },
  { id: 'cockpit', label: 'Decision cockpit' },
  { id: 'ribbon', label: 'Day ribbon' },
  { id: 'story', label: 'Story' },
];

interface State {
  data: Results | null;
  error: string | null;
  /** which results the views show: the validation year, or the sealed test year once it is run (T11) */
  evalWindow: EvalWindow;
  /** results/test as copy-data found it; the test option is enabled only when its manifest exists */
  testIndex: ResultsIndex['test'] | null;
  page: Page;
  /** the Story page's view; kept while another page is open, so the Story tab returns to it */
  view: View;
  hour: number;
  month: string;
  mode: Mode;
  dest: Dest;
  arcPolicy: 'S' | 'W' | 'L';
  scenario: ScenarioId;
  gpus: number;
  hours: number;
  maxWait: number;
  step: number;
  drawer: boolean;
  set: (p: Partial<State>) => void;
}

/** Plain hash routing: "#<page>" for a standalone page, any other hash (or none) is the Story page, whose
 * view is the hash's first segment (#control, #cockpit, #ribbon, #story, #story-N); unknown hashes show the
 * control room, as before the shell. */
export function parseRoute(hash = location.hash): { page: Page; view: View | null } {
  const h = hash.replace('#', '').split('-')[0];
  const page = PAGES.find((p) => p.id === h && p.id !== 'story')?.id;
  if (page) return { page, view: null };
  return { page: 'story', view: (VIEWS.find((v) => v.id === h)?.id ?? 'control') as View };
}
const route0 = parseRoute();

/** The year the dashboard opens in: `?year=test` or `?year=validation` in the URL (the pitch deck's links,
 * e.g. /?year=test#story-3), else the year last chosen in this browser, else the validation year. Storage can
 * be missing or blocked (private window): every access is guarded and falls back to validation. */
export const YEAR_KEY = 'gridpilot.evalWindow';
export function initialWindow(search = location.search): EvalWindow {
  const q = new URLSearchParams(search).get('year');
  if (q === 'test' || q === 'validation') { rememberWindow(q); return q; } // a link's year is a choice too
  try { const v = localStorage.getItem(YEAR_KEY); if (v === 'test' || v === 'validation') return v; } catch { /* storage unavailable */ }
  return 'validation';
}
export function rememberWindow(w: EvalWindow) {
  try { localStorage.setItem(YEAR_KEY, w); } catch { /* storage unavailable: the choice lasts for this visit */ }
}

export const useApp = create<State>((set) => ({
  data: null,
  error: null,
  evalWindow: initialWindow(),
  testIndex: null,
  page: route0.page,
  view: route0.view ?? 'control',
  hour: 19,
  month: '2025-07',
  mode: 'move',
  dest: 'BPAT',
  arcPolicy: 'S', // F23: S, the likely deployed choice, is the default
  scenario: 'registered',
  gpus: 64,
  hours: 8,
  maxWait: 6,
  step: 1,
  drawer: false,
  set: (p) => set(p),
}));

/** The story beat a #story-N hash names (1–6), or null. */
export const parseStep = (): number | null => { const m = /^#story-(\d)$/.exec(location.hash); return m ? Math.min(6, Math.max(1, Number(m[1]))) : null; };
export const initialStep = parseStep();
// remember the year switch's choice for the next visit (and the next deep link)
useApp.subscribe((s, prev) => { if (s.evalWindow !== prev.evalWindow) rememberWindow(s.evalWindow); });
if (initialStep) useApp.setState({ step: initialStep });
window.addEventListener('hashchange', () => {
  const st = parseStep(), r = parseRoute();
  // leaving the Story page closes its method drawer (the Evidence page carries the same content)
  useApp.getState().set({ page: r.page, ...(r.view ? { view: r.view } : {}), ...(st ? { step: st } : {}), ...(r.page !== 'story' ? { drawer: false } : {}) });
});
