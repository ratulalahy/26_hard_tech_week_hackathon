// Screenshots for the viz-critique loop: every view at 1440×900 and 1728×1117 into docs/design/shots-build/.
//   npm run build && npx playwright test tests/shots.spec.ts          (SHOTS=control,cockpit to limit)
import { test, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const out = process.env.SHOTS_DIR ?? join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'docs', 'design', 'shots-build');
mkdirSync(out, { recursive: true });
const only = process.env.SHOTS?.split(',');
const SIZES = [{ w: 1728, h: 1117 }, { w: 1440, h: 900 }];
const STATES: { name: string; hash: string; prep?: (p: Page) => Promise<void> }[] = [
  { name: 'control', hash: '#control' },
  { name: 'control-zoomed', hash: '#control', prep: async (p) => { await p.getByRole('button', { name: 'Zoom in' }).click(); await p.waitForTimeout(400); await p.getByRole('button', { name: 'Zoom in' }).click(); await p.waitForTimeout(700); } },
  { name: 'cockpit', hash: '#cockpit' },
  { name: 'cockpit-wait', hash: '#cockpit', prep: async (p) => { await p.getByRole('group', { name: 'Router action' }).getByRole('button', { name: 'Wait' }).click(); } },
  { name: 'ribbon', hash: '#ribbon' },
  { name: 'story-1', hash: '#story' },
  { name: 'story-4', hash: '#story', prep: async (p) => { await p.locator('[data-step="4"]').scrollIntoViewIfNeeded(); await p.waitForTimeout(600); } },
  { name: 'method', hash: '#control', prep: async (p) => { await p.getByRole('button', { name: 'Method & evidence' }).click(); await p.waitForTimeout(300); } },
];

for (const s of SIZES) {
  for (const st of STATES) {
    if (only && !only.some((o) => st.name.startsWith(o))) continue;
    test(`${st.name} ${s.w}`, async ({ page }) => {
      await page.setViewportSize({ width: s.w, height: s.h });
      await page.goto('./' + st.hash);
      await page.locator('.mk-region').first().waitFor({ timeout: 20_000 });
      await page.waitForTimeout(1200);
      if (st.prep) await st.prep(page);
      await page.waitForTimeout(500);
      await page.screenshot({ path: join(out, `${st.name}-${s.w}.png`) });
    });
  }
}
