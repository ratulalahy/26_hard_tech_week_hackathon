import { windowCopy, type WindowCopy } from './copy';
import { useApp } from './store';

/** The copy for the window being shown (validation until results load). Kept apart from copy.ts so that
 * the pure helpers (and lib/plan.ts's tests) never load the store. */
export function useCopy(): WindowCopy {
  const { data, evalWindow } = useApp();
  return windowCopy(data ? evalWindow : 'validation', data?.manifest);
}
