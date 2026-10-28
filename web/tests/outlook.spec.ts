// T19: the grid outlook page renders from results/outlook.json, offline, and labels a demo as a demo.
import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

const LOCAL = new Set(['127.0.0.1', 'localhost', '[::1]']);
const outlook = JSON.parse(readFileSync(new URL('../public/data/results/outlook.json', import.meta.url), 'utf8'));

test('the outlook page shows every day, the router pick and the skill table, offline', async ({ page }) => {
  const blocked: string[] = [];
  await page.context().route('**/*', (route) => {
    const u = new URL(route.request().url());
    if (u.protocol.startsWith('http') && !LOCAL.has(u.hostname)) { blocked.push(u.href); return route.abort('blockedbyclient'); }
    return route.continue();
  });
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto('./#outlook');
  await expect(page.getByTestId('outlook-title')).toBeVisible();
  await expect(page.getByTestId('outlook-days').locator('li')).toHaveCount(outlook.days.length);
  await expect(page.getByTestId('outlook-days')).toContainText('Router S → Northwest hydro');
  await expect(page.getByTestId('outlook-ranking').locator('li')).toHaveCount(4);
  // M1: no skill claim for Utah unless a cell clears the block-bootstrap rule
  const utahPass = Object.values(outlook.skill_by_horizon.PACE).some((c: any) => c.status === 'forecast'); // eslint-disable-line @typescript-eslint/no-explicit-any
  if (!utahPass) {
    await expect(page.getByTestId('outlook-skill-line')).toContainText("Utah's forecast is not reliably better than its seasonal average");
    await expect(page.getByTestId('outlook-days')).not.toContainText('better than avg');
  }
  await expect(page.getByRole('radiogroup', { name: 'Evaluation window' })).toHaveCount(0);
  await expect(page.getByTestId('outlook-skill').locator('tbody tr')).toHaveCount(4);
  for (const ba of ['PACE', 'BPAT', 'CISO', 'NEVP']) await expect(page.getByTestId(`outlook-chart-${ba}`).locator('svg')).toBeVisible();
  if (outlook.demo) await expect(page.getByTestId('outlook-demo')).toContainText('DEMO · validation date');
  else await expect(page.getByTestId('outlook-demo')).toHaveCount(0);
  expect(blocked).toEqual([]);
  expect(errors).toEqual([]);
  if (process.env.OUTLOOK_SHOTS) {
    for (const [w, h] of [[1440, 900], [1728, 1117]]) {
      await page.setViewportSize({ width: w, height: h });
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${process.env.OUTLOOK_SHOTS}/outlook-${w}.png`, fullPage: false });
    }
  }
});
