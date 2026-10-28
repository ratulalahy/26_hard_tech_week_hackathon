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
  // the hero is the range over the two California load zones, and says so
  const [lo, hi] = prices.california_node.range.W.delta_vs_U_usd.value as [number, number];
  const k = `$${Math.round(Math.abs(lo) / 1000)}–${Math.round(Math.abs(hi) / 1000)}k`;
  await expect(page.getByTestId('prices-title')).toContainText(k);
  await expect(page.getByTestId('prices-title')).toContainText('depending on the California load zone');
  await expect(page.getByTestId('prices-title')).toContainText(`Over ${prices.policies.W.interval.blocks[String(prices.policies.W.interval.primary_block.value)].n_weeks.value} weeks`);
  await expect(page.getByTestId('prices-card-hero')).toContainText(k);
  await expect(page.getByTestId('prices-whisker-note')).toContainText('not the price-node choice');
  await expect(page.getByTestId('prices-per-tonne-note')).toBeVisible();
  const mob = prices.policies['mobility_le_8gpus:W'];
  if (mob) {
    const [a, b] = mob.interval.blocks[String(mob.interval.primary_block.value)].delta_vs_U_usd_ci95.value;
    if (a < 0 && b > 0) await expect(page.getByTestId('prices-card-mob')).toContainText('interval spans zero');
  }
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
