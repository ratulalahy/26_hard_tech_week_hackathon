// Screenshots for the viz-critique loop: every view at 1440×900 and 1728×1117 into docs/design/shots-build/.
//   npm run build && npx playwright test tests/shots.spec.ts          (SHOTS=control,cockpit to limit)
import { test, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openTestYear, serveTestFixture } from './fixture-route';

const out = process.env.SHOTS_DIR ?? join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'docs', 'design', 'shots-build');
mkdirSync(out, { recursive: true });
const only = process.env.SHOTS?.split(',');
const SIZES = [{ w: 1728, h: 1117 }, { w: 1440, h: 900 }];
const STATES: { name: string; hash: string; prep?: (p: Page) => Promise<void> }[] = [
  { name: 'control', hash: '#control' },
  { name: 'control-zoomed', hash: '#control', prep: async (p) => { await p.getByRole('button', { name: 'Zoom in' }).click(); await p.waitForTimeout(400); await p.getByRole('button', { name: 'Zoom in' }).click(); await p.waitForTimeout(700); } },
  // T15: the four toggle states (the budget sits in the right dock) and story 4 with the toggle
  ...([['registered', 0], ['mobility', 1], ['wait0', 2], ['double', 3]] as const).map(([n, i]) => ({ name: `control-toggle-${n}`, hash: '#control', prep: async (p: Page) => { await p.getByTestId('scenario-toggle').getByRole('button').nth(i).click(); await p.waitForTimeout(500); } })),
  { name: 'story-4-mobility', hash: '#story-4', prep: async (p) => { await p.waitForTimeout(900); await p.getByTestId('scenario-toggle').getByRole('button').nth(1).click(); await p.waitForTimeout(600); } },
  { name: 'cockpit', hash: '#cockpit' },
  { name: 'cockpit-wait', hash: '#cockpit', prep: async (p) => { await p.getByRole('group', { name: 'Router action' }).getByRole('button', { name: 'Wait' }).click(); } },
  { name: 'ribbon', hash: '#ribbon' },
  // T16: the toughest-days card on its third day
  ...[2, 3].map((n) => ({ name: `ribbon-case-${n}`, hash: '#ribbon', prep: async (p: Page) => { await p.getByRole('radiogroup', { name: 'Toughest days' }).getByRole('radio').nth(n - 1).click(); await p.waitForTimeout(300); } })),
  ...[1, 2, 3, 4, 5, 6].map((n) => ({ name: `story-${n}`, hash: `#story-${n}`, prep: async (p: Page) => { await p.waitForTimeout(900); } })),
  { name: 'method', hash: '#control', prep: async (p) => { await p.getByRole('button', { name: 'Method & evidence' }).click(); await p.waitForTimeout(300); } },
  { name: 'method-checks', hash: '#control', prep: async (p) => { await p.getByRole('button', { name: 'Method & evidence' }).click(); await p.waitForTimeout(300); await p.getByTestId('method-extensions').scrollIntoViewIfNeeded(); await p.waitForTimeout(300); } },
  // T18: the standalone ten-region overview page
  { name: 'regions', hash: '#regions' },
  { name: 'regions-table', hash: '#regions', prep: async (p) => { await p.getByTestId('regions-table').scrollIntoViewIfNeeded(); await p.waitForTimeout(300); } },
  { name: 'regions-multiples', hash: '#regions', prep: async (p) => { await p.getByTestId('regions-multiples').scrollIntoViewIfNeeded(); await p.waitForTimeout(300); } },
  // T11: the test-year state on the SYNTHETIC fixture (never real test results)
  { name: 'fixture-test-control', hash: '#control', prep: async (p) => { await openTestYear(p); await p.waitForTimeout(1200); } },
  { name: 'fixture-test-method', hash: '#control', prep: async (p) => { await openTestYear(p); await p.waitForTimeout(800); await p.getByRole('button', { name: 'Method & evidence' }).click(); await p.waitForTimeout(300); } },
];

for (const s of SIZES) {
  for (const st of STATES) {
    if (only && !only.some((o) => st.name.startsWith(o))) continue;
    test(`${st.name} ${s.w}`, async ({ page }) => {
      await page.setViewportSize({ width: s.w, height: s.h });
      if (st.name.startsWith('fixture-test')) await serveTestFixture(page);
      await page.goto('./' + st.hash);
      await page.locator(st.hash === '#regions' ? '.mk-ov' : '.mk-region').first().waitFor({ state: 'attached', timeout: 20_000 });
      await page.waitForTimeout(1200);
      if (st.prep) await st.prep(page);
      await page.waitForTimeout(500);
      await page.screenshot({ path: join(out, `${st.name}-${s.w}.png`) });
    });
  }
}
