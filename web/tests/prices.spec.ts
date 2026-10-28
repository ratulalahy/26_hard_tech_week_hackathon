// T22: the price lens renders from results/prices.json, offline, says "wholesale scenario" before any
// number, and states the sign of moving's cost honestly.
import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

const LOCAL = new Set(['127.0.0.1', 'localhost', '[::1]']);
const prices = JSON.parse(readFileSync(new URL('../public/data/results/prices.json', import.meta.url), 'utf8'));

test('the price lens shows the caveat, the honest headline and both charts, offline', async ({ page }) => {
  const blocked: string[] = [];
  await page.context().route('**/*', (route) => {
    const u = new URL(route.request().url());
    if (u.protocol.startsWith('http') && !LOCAL.has(u.hostname)) { blocked.push(u.href); return route.abort('blockedbyclient'); }
    return route.continue();
  });
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto('./#prices');
  await expect(page.getByTestId('prices-caveat').first()).toContainText('Wholesale scenario');
  await expect(page.getByTestId('prices-caveat').first()).toContainText('retail tariff');
  const w = prices.policies.W.delta_vs_U_usd.value as number;
  await expect(page.getByTestId('prices-title')).toContainText(w > 0 ? 'costs more' : 'saves money');
  const k = `$${Math.round(Math.abs(w)).toLocaleString('en-US')}`;
  await expect(page.getByTestId('prices-title')).toContainText(k);
  await expect(page.getByTestId('prices-card-hero')).toContainText(k);
  await expect(page.getByTestId('prices-card')).toContainText('Wholesale scenario');
  for (const id of ['prices-delta', 'prices-profile']) await expect(page.getByTestId(id).locator('svg')).toBeVisible();
  const n = Object.keys(prices.policies).length - 1; // every policy but U
  await expect(page.getByTestId('prices-split').locator('tbody tr')).toHaveCount(n);
  await expect(page.getByTestId('prices-delta-table').locator('tbody tr')).toHaveCount(n);
  const body = (await page.locator('body').innerText()).toLowerCase();
  expect(body).not.toContain('avoided');
  expect(body).not.toContain('abatement cost');
  expect(blocked).toEqual([]);
  expect(errors).toEqual([]);
  if (process.env.PRICES_SHOTS) {
    for (const [wd, h] of [[1440, 900], [1728, 1117], [390, 844]]) {
      await page.setViewportSize({ width: wd, height: h });
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${process.env.PRICES_SHOTS}/prices-${wd}.png`, fullPage: false });
    }
  }
});
