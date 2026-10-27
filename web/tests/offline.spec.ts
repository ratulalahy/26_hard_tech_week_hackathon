// Offline acceptance (Task 8 Step 1): the built dist/, served on localhost, makes no request to any other
// host, and every view renders a value that comes from results/metrics.json.
import { expect, test, type Page } from '@playwright/test';
import { consumptionSpan, lCommonSupport, mobilityAbout, placementRange, sProduction, sTonnes, storageCombined, storageFlatT, storageHeadline, storageRushDays, storageRushN, timeOnlyRange, uTonnes } from './expected';

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
  await expect(page.getByRole('heading', { level: 1 })).toContainText("In a simulated replay, moving Utah's AI jobs cut their CO₂ by a fifth. Waiting barely helps.");
  await expect(page.getByTestId('hero-frame')).toHaveText('Replay of a measured GPU-cluster trace mapped onto Utah · deadlines relative to the baseline, met by construction · exact declared runtimes; runtime uncertainty untested.');
  await expect(hero).toContainText('deadlines met by construction (baseline bookings)');
  await expect(page.getByTestId('hero-mobility')).toContainText(`if only jobs of 8 GPUs or fewer could move, it would be ${mobilityAbout}`);
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
  // T10b (F18, fix r1): story 6 is the storage illustration, from results/storage.json
  await page.goto('./#story-6');
  await expect(page.getByTestId('storage-headline')).toContainText(storageHeadline);
  await expect(page.getByTestId('storage-combined')).toContainText(storageCombined);
  await expect(page.getByTestId('storage-skeptic')).toContainText(`On a flat marginal basis it may add about ${storageFlatT} t: storage only helps if charging carbon ÷ η < displaced carbon.`);
  await expect(page.getByTestId('storage-curve')).toBeVisible();
  await expect(page.getByTestId('storage-import')).toBeVisible();
  await expect(page.getByText('illustrative · not the registered result')).toBeVisible();

  await page.getByRole('banner').getByRole('button', { name: 'Method & evidence' }).click();
  const drawer = page.getByRole('dialog');
  await expect(drawer).toContainText('simulated advance-reservation scheduling scenario; baseline-relative deadlines');
  await expect(drawer).toContainText("A job's deadline is the later of (a) its run-now finish plus its allowed delay and (b) its finish in the stay-in-Utah baseline (baseline-relative).");
  await expect(drawer.getByTestId('validation-line')).toHaveText('These are validation-year results, which shaped the design; the sealed test year is the real test.');
  await expect(drawer).toContainText("ignores competition between jobs for capacity (each job's own limits still apply)");
  await expect(drawer.getByTestId('policy-table')).toContainText(sTonnes);
  await expect(drawer.getByTestId('policy-table')).toContainText(uTonnes);
  await expect(drawer.getByTestId('method-extensions')).toContainText(sProduction);
  // T10: the D-058 checks, moved from the story to the drawer (F18)
  await expect(drawer.getByTestId('method-extensions')).toContainText(lCommonSupport);
  await expect(drawer.getByTestId('method-checks')).toContainText(`still cut ${consumptionSpan}`);
  await expect(drawer.getByTestId('method-checks')).toContainText('production basis flatters hydro-heavy destinations');
  await expect(drawer.getByTestId('method-storage')).toContainText('not part of the registered experiment'.replace(/^./, (c) => c.toUpperCase()));
  await expect(drawer.getByTestId('storage-relief')).toContainText('W weekly profile');
  await expect(drawer.getByTestId('method-rush')).toContainText(`${storageRushN} hours on ${storageRushDays} days`);
  await expect(drawer.getByTestId('method-breakeven')).toContainText('On our rough reference the charging hours are no cleaner on the margin');
  await expect(drawer.getByTestId('storage-rush-sens')).toBeVisible();

  await page.waitForLoadState('networkidle');
  expect(errors, 'page errors').toEqual([]);
  expect(g.blocked, 'blocked non-localhost requests').toEqual([]);
  const foreign = g.seen.filter((u) => /^(https?|wss?):/.test(u) && !LOCAL.has(new URL(u).hostname));
  expect(foreign, 'non-localhost requests attempted').toEqual([]);
  expect(g.seen.length).toBeGreaterThan(5);
});
