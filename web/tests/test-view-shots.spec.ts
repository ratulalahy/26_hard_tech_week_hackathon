// Screenshots of the sealed test-year view (results/test, opened once) at the two review sizes.
// Run on demand: PW_PORT=<port> npx playwright test tests/test-view-shots.spec.ts
import { join } from 'node:path';
import { test } from '@playwright/test';
import { openTestYear } from './fixture-route';

const OUT = join(process.cwd(), '..', 'docs', 'design', 'shots-build');
const SHOTS: { name: string; hash: string; drawer?: string }[] = [
  { name: 'test-control', hash: '#control' },
  { name: 'test-story-3', hash: '#story-3' },
  { name: 'test-story-4', hash: '#story-4' },
  { name: 'test-story-5', hash: '#story-5' },
  { name: 'test-ribbon', hash: '#ribbon' },
  { name: 'test-method-drift', hash: '#control', drawer: 'drift-view' },
  { name: 'test-method-storage', hash: '#control', drawer: 'method-storage-test' },
];
for (const [w, h] of [[1440, 900], [1728, 1117]] as const) {
  for (const s of SHOTS) {
    test(`shot ${s.name} ${w}`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: h });
      await page.goto('./' + s.hash);
      await page.locator('.mk-region').first().waitFor({ state: 'attached' });
      await openTestYear(page);
      await page.waitForTimeout(1200);
      if (s.drawer) {
        await page.getByRole('banner').getByRole('button', { name: 'Method & evidence' }).click();
        await page.getByTestId(s.drawer).scrollIntoViewIfNeeded();
        await page.waitForTimeout(300);
      }
      await page.screenshot({ path: join(OUT, `${s.name}-${w}.png`) });
    });
  }
}
