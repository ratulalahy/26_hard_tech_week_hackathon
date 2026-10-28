// T21 screenshots for the viz-critique loop: every page of the nav shell at 1440, 1728 and 390 px into
// docs/design/shots-build/t21-<page>-<width>.png. npm run build && npx playwright test tests/t21-shots.spec.ts
import { test, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const out = process.env.SHOTS_DIR ?? join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'docs', 'design', 'shots-build');
mkdirSync(out, { recursive: true });
const only = process.env.SHOTS?.split(',');
const SIZES = [{ w: 1728, h: 1117 }, { w: 1440, h: 900 }, { w: 390, h: 844 }];
const ready = async (p: Page, sel: string) => { await p.locator(sel).first().waitFor({ state: 'attached', timeout: 20_000 }); await p.waitForTimeout(1200); };
const STATES: { name: string; hash: string; prep: (p: Page) => Promise<void> }[] = [
  { name: 'control', hash: '#control', prep: (p) => ready(p, '.mk-region') },
  { name: 'story-1', hash: '#story-1', prep: (p) => ready(p, '.mk-region') },
  { name: 'monitor', hash: '#monitor', prep: (p) => ready(p, '[data-testid="monitor-feed"] li') },
  { name: 'monitor-playing', hash: '#monitor', prep: async (p) => { await ready(p, '[data-testid="monitor-feed"] li'); await p.getByTestId('monitor-scrub').fill('125'); await p.waitForTimeout(300); } },
  { name: 'outlook', hash: '#outlook', prep: (p) => ready(p, '[data-testid="outlook-days"] li') },
  { name: 'regions', hash: '#regions', prep: (p) => ready(p, '.mk-ov') },
  { name: 'prices', hash: '#prices', prep: (p) => ready(p, '[data-testid="prices-title"]') },
  { name: 'evidence', hash: '#evidence', prep: (p) => ready(p, '[data-testid="evidence-title"]') },
  { name: 'evidence-test', hash: '#evidence', prep: async (p) => { await ready(p, '[data-testid="evidence-title"]'); await p.getByRole('radio', { name: /^Test year/ }).click(); await p.locator('[data-testid="evidence-title"]').waitFor(); await p.waitForTimeout(1200); } },
];

for (const s of SIZES) {
  for (const st of STATES) {
    if (only && !only.some((o) => st.name.startsWith(o))) continue;
    test(`t21 ${st.name} ${s.w}`, async ({ page }) => {
      await page.setViewportSize({ width: s.w, height: s.h });
      await page.goto('./' + st.hash);
      await st.prep(page);
      await page.screenshot({ path: join(out, `t21-${st.name}-${s.w}.png`) });
    });
  }
}
