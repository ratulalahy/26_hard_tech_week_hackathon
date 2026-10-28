import { create } from 'zustand';
import type { EvalWindow } from './copy';
import type { Dest, Results, ResultsIndex } from './data';

export type View = 'control' | 'cockpit' | 'ribbon' | 'story' | 'prices';
export type Mode = 'now' | 'wait' | 'move';
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
  view: View;
  hour: number;
  month: string;
  mode: Mode;
  dest: Dest;
  arcPolicy: 'S' | 'W' | 'L';
  gpus: number;
  hours: number;
  maxWait: number;
  step: number;
  drawer: boolean;
  set: (p: Partial<State>) => void;
}

const parseView = (): View => {
  const h = location.hash.replace('#', '').split('-')[0];
  if (h === 'prices') return 'prices'; // T22: a standalone page at #prices, outside the tab bar (the nav shell mounts it)
  return (VIEWS.find((v) => v.id === h)?.id ?? 'control') as View;
};

export const useApp = create<State>((set) => ({
  data: null,
  error: null,
  evalWindow: 'validation',
  testIndex: null,
  view: parseView(),
  hour: 19,
  month: '2025-07',
  mode: 'move',
  dest: 'BPAT',
  arcPolicy: 'W',
  gpus: 64,
  hours: 8,
  maxWait: 6,
  step: 1,
  drawer: false,
  set: (p) => set(p),
}));

const parseStep = (): number | null => { const m = /^#story-(\d)$/.exec(location.hash); return m ? Math.min(6, Math.max(1, Number(m[1]))) : null; };
export const initialStep = parseStep();
if (initialStep) useApp.setState({ step: initialStep });
window.addEventListener('hashchange', () => { const st = parseStep(); useApp.getState().set({ view: parseView(), ...(st ? { step: st } : {}) }); });
