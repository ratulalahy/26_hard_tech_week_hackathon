// Offline acceptance (Task 8 Step 1): the built dist/, served on localhost, makes no request to any other
// host, and every view renders a value that comes from results/metrics.json.
import { expect, test, type Page } from '@playwright/test';
import { placementRange, sTonnes, timeOnlyRange, uTonnes } from './expected';

const LOCAL = new Set(['127.0.0.1', 'localhost', '[::1]']);

function guard(page: Page) {
  const blocked: string[] = [];
  const seen: string[] = [];
  page.on('request', (r) => seen.push(r.url()));
  return {
    blocked,
    seen,
    install: () =>
      page.context().route('**/*', (route) => {
        const u = new URL(route.request().url());
        if ((u.protocol === 'http:' || u.protocol === 'https:' || u.protocol === 'ws:' || u.protocol === 'wss:') && !LOCAL.has(u.hostname)) {
          blocked.push(u.href);
          return route.abort('blockedbyclient');
        }
        return route.continue();
      }),
  };
}

test('every view renders registered values with zero non-localhost requests', async ({ page }) => {
  const g = guard(page);
  await g.install();
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));

  await page.goto('./#control');
  const hero = page.getByTestId('hero-placement');
  await expect(hero).toContainText(placementRange);
  await expect(page.getByTestId('hero-timing')).toContainText(timeOnlyRange);
  await expect(page.getByText('Validation year (Nov 2024 – Oct 2025) · test year sealed').first()).toBeVisible();
  // the map is drawn locally: a WebGL canvas and the four core regions labelled on it
  await expect(page.locator('#map-main canvas.maplibregl-canvas')).toBeVisible();
  for (const label of ['Utah · PACE', 'Northwest hydro · BPAT', 'California · CISO', 'Nevada · NEVP']) {
    await expect(page.locator('#map-main').getByText(label, { exact: true })).toBeVisible();
  }

  await page.goto('./#cockpit');
  await expect(page.getByTestId('cockpit-registered')).toContainText(placementRange);
  await expect(page.getByTestId('cockpit-registered')).toContainText(timeOnlyRange);
  await expect(page.getByText('illustrative · modeled').first()).toBeVisible();

  await page.goto('./#ribbon');
  await expect(page.getByTestId('ribbon-timing')).toContainText(timeOnlyRange);
  await expect(page.getByTestId('forecast-chart')).toBeVisible();

  await page.goto('./#story');
  await expect(page.getByTestId('story-result')).toContainText(placementRange);

  await page.getByRole('banner').getByRole('button', { name: 'Method & evidence' }).click();
  const drawer = page.getByRole('dialog');
  await expect(drawer).toContainText('simulated advance-reservation scheduling scenario; baseline-relative deadlines');
  await expect(drawer.getByTestId('policy-table')).toContainText(sTonnes);
  await expect(drawer.getByTestId('policy-table')).toContainText(uTonnes);

  await page.waitForLoadState('networkidle');
  expect(errors, 'page errors').toEqual([]);
  expect(g.blocked, 'blocked non-localhost requests').toEqual([]);
  const foreign = g.seen.filter((u) => /^(https?|wss?):/.test(u) && !LOCAL.has(new URL(u).hostname));
  expect(foreign, 'non-localhost requests attempted').toEqual([]);
  expect(g.seen.length).toBeGreaterThan(5);
});
