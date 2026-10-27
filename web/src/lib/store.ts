import { create } from 'zustand';
import type { Dest, Results } from './data';

export type View = 'control' | 'cockpit' | 'ribbon' | 'story';
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
  return (VIEWS.find((v) => v.id === h)?.id ?? 'control') as View;
};

export const useApp = create<State>((set) => ({
  data: null,
  error: null,
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

window.addEventListener('hashchange', () => useApp.getState().set({ view: parseView() }));
