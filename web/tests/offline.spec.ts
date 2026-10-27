// Offline acceptance (Task 8 Step 1): the built dist/, served on localhost, makes no request to any other
// host, and every view renders a value that comes from results/metrics.json.
import { expect, test, type Page } from '@playwright/test';
import { bpatGpuH, budgetHeadline, consumptionSpan, fixtureManifest, lCommonSupport, sAbout, sMobility, sOwn, sOwnCI, sProduction, sTonnes, storageCombined, storageFlatT, storageHeadline, storageRushDays, storageRushN, testSOwn, testTimeOnlyRange, timeOnlyRange, uTonnes } from './expected';
import { openTestYear, serveTestFixture } from './fixture-route';

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
  // F06 and F10: the headline is S's own estimate and interval; no "30×", no span across policies
  await expect(hero).toContainText(sOwn);
  await expect(hero).toContainText(`Its own 95% interval ${sOwnCI}`);
  await expect(page.getByTestId('hero-kind')).toContainText('registered result');
  await expect(page.getByTestId('hero-timing')).toContainText('under 1%');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(`In a simulated replay, moving Utah's AI jobs cut their attributed CO₂ by about ${sAbout}%; waiting in Utah cut under 1%.`);
  await expect(page.getByTestId('hero-frame')).toHaveText('Replay of a measured GPU-cluster trace mapped onto Utah · deadlines relative to the baseline, met by construction · exact declared runtimes; runtime uncertainty untested.');
  await expect(hero).toContainText('deadlines met by construction (baseline bookings)');
  await expect(page.getByTestId('hero-mobility')).toContainText(`${sOwn} → ${sMobility} if only jobs of 8 GPUs or fewer may move`);
  await expect(page.getByTestId('budget-headline').first()).toHaveText(budgetHeadline);
  // T11: the window switch shows the validation year; the test year stays sealed (disabled) until results/test exists
  await expect(page.getByRole('radio', { name: 'Validation year' })).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByRole('radio', { name: 'Test year (sealed until the freeze)' })).toBeDisabled();
  await expect(page.getByTestId('window-switch')).toHaveAccessibleDescription('Validation year (Nov 2024 – Oct 2025) · test year sealed');
  // the map is drawn locally: a WebGL canvas and the four core regions labelled on it
  await expect(page.locator('#map-main canvas.maplibregl-canvas')).toBeVisible();
  for (const label of ['Utah · PACE', 'Northwest hydro · BPAT', 'California · CISO', 'Nevada · NEVP']) {
    await expect(page.locator('#map-main').getByText(label, { exact: true })).toBeVisible();
  }

  await page.goto('./#cockpit');
  await expect(page.getByTestId('cockpit-registered')).toContainText(sOwn);
  await expect(page.getByTestId('cockpit-registered')).toContainText('under 1%');
  await expect(page.getByText('illustrative · modeled').first()).toBeVisible();
  await expect(page.getByTestId('cockpit-caption')).toHaveText('one hypothetical job; typical-day profile; capacity unconstrained');

  await page.goto('./#ribbon');
  await expect(page.getByTestId('ribbon-timing')).toContainText(timeOnlyRange);
  await expect(page.getByTestId('forecast-chart')).toBeVisible();
  await expect(page.getByText('retrospective ±week MAE; not a prediction interval').first()).toBeVisible();

  await page.goto('./#story');
  await expect(page.getByTestId('story-result')).toContainText(sOwn);
  await expect(page.getByTestId('story-result')).toContainText('no demonstrated aggregate benefit from dynamic search in this replay');
  // T10b (F18, fix r1): story 5 (D-064 order) is the storage illustration, from results/storage.json
  await page.goto('./#story-5');
  await expect(page.getByTestId('storage-headline')).toContainText(storageHeadline);
  await expect(page.getByTestId('storage-combined')).toContainText(storageCombined);
  await expect(page.getByTestId('storage-skeptic')).toContainText(`On a flat marginal basis it may add about ${storageFlatT} t: storage only helps if charging carbon ÷ η < displaced carbon.`);
  await expect(page.getByTestId('storage-curve')).toBeVisible();
  await expect(page.getByTestId('storage-import')).toBeVisible();
  await expect(page.getByText('illustrative · not the registered result')).toBeVisible();
  // D-064 beat 6, the evidence: the D-058 checks as scenario estimates; the full table is in the drawer (F18)
  await page.goto('./#story-6');
  await expect(page.getByTestId('story-checks')).toContainText(`still cut ${consumptionSpan}: scenario estimates`);
  await expect(page.getByTestId('story-checks')).toContainText('production basis flatters hydro-heavy destinations');

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
  await expect(drawer.getByTestId('method-dynamic')).toContainText('no demonstrated aggregate benefit from dynamic search in this replay');

  await page.waitForLoadState('networkidle');
  expect(errors, 'page errors').toEqual([]);
  expect(g.blocked, 'blocked non-localhost requests').toEqual([]);
  const foreign = g.seen.filter((u) => /^(https?|wss?):/.test(u) && !LOCAL.has(new URL(u).hostname));
  expect(foreign, 'non-localhost requests attempted').toEqual([]);
  expect(g.seen.length).toBeGreaterThan(5);
});

test('the test-year state shows only test numbers and no validation wording (synthetic fixture)', async ({ page }) => {
  const g = guard(page);
  await g.install();
  await serveTestFixture(page);
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  const noValidation = async (where: string) => {
    for (const loc of [page.locator('main'), page.locator('footer')]) {
      const t = (await loc.innerText()).toLowerCase();
      expect(t.includes('validation'), `${where}: validation wording on test numbers`).toBe(false);
      // M14: the test year covers a period, not a full year
      expect(/all year|over the year|the year's|whole year/.test(t), `${where}: "year" wording on test numbers`).toBe(false);
    }
  };

  await page.goto('./#control');
  await expect(page.getByTestId('hero-placement')).toContainText(sOwn);
  await openTestYear(page);
  await expect(page.getByRole('radio', { name: 'Test year (sealed until Oct 27)' })).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByTestId('hero-placement')).toContainText(testSOwn); // F10: S's own estimate
  await expect(page.getByTestId('hero-timing')).toContainText(testTimeOnlyRange);
  await expect(page.getByRole('heading', { level: 1 })).toContainText(`moving Utah's AI jobs cut their CO₂ by ${testSOwn}`);
  await expect(page.getByTestId('window-switch')).toHaveAccessibleDescription(/^Test year \(Nov 2025 – Oct 2026\) · opened once, after the freeze of Oct 27, 2026$/);
  await noValidation('control');

  for (const [tab, id, want] of [['Decision cockpit', 'cockpit-registered', testSOwn], ['Day ribbon', 'ribbon-timing', testTimeOnlyRange], ['Story', 'story-result', testSOwn]] as const) {
    await page.getByRole('navigation', { name: 'Views' }).getByRole('link', { name: tab }).click();
    await expect(page.getByTestId(id)).toContainText(want);
    await noValidation(tab);
  }
  await expect(page.getByTestId('story-result')).toContainText('Over the test year');

  await page.getByRole('banner').getByRole('button', { name: 'Method & evidence' }).click();
  const drawer = page.getByRole('dialog');
  await expect(drawer.getByTestId('test-line')).toHaveText('These are sealed test-year results: the year was opened once, after the model and policy settings were frozen, and nothing was tuned on it.');
  await expect(drawer).toContainText('Every policy, the test cohort');
  await expect(drawer).toContainText(fixtureManifest.run_id);
  expect((await drawer.innerText()).toLowerCase().includes('validation'), 'drawer: validation wording').toBe(false);
  await page.keyboard.press('Escape');

  // back to the validation year: its numbers and wording return
  await page.getByRole('radio', { name: 'Validation year' }).click();
  await expect(page.getByTestId('story-result')).toContainText(sOwn);
  await expect(page.getByTestId('story-result')).toContainText('Over the validation year');

  await page.waitForLoadState('networkidle');
  expect(errors, 'page errors').toEqual([]);
  expect(g.blocked, 'blocked non-localhost requests').toEqual([]);
});

test('the synthetic test fixture is never published under public/', async () => {
  const { existsSync, readFileSync } = await import('node:fs');
  const { join } = await import('node:path');
  const pub = join(process.cwd(), 'public', 'data', 'results');
  const idx = JSON.parse(readFileSync(join(pub, 'index.json'), 'utf8'));
  const man = join(pub, 'test', 'manifest.json');
  if (existsSync(man)) {
    expect(JSON.parse(readFileSync(man, 'utf8')).fixture, 'a fixture manifest under public/').toBeUndefined();
    expect(idx.test.available).toBe(true);
  } else {
    expect(idx.test?.available ?? false).toBe(false);
  }
});

// T15 (D-064): the "Which jobs can move?" toggle switches the hero, the rows and the arcs to that scenario's estimate.
test('the mobility/capacity toggle switches the hero, rows and arcs; registered by default', async ({ page }) => {
  await page.goto('./#control');
  const toggle = page.getByTestId('scenario-toggle');
  const btn = (i: number) => toggle.getByRole('button').nth(i);
  await expect(btn(0)).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByLabel('Policy shown on the map')).toHaveValue('S'); // F23: S by default
  await expect(page.getByTestId('work-rows')).toContainText(bpatGpuH('registered'));
  await btn(1).click();
  await expect(page.getByTestId('hero-kind')).toContainText('scenario estimate (validation)');
  await expect(page.getByTestId('hero-placement')).toContainText(sMobility);
  await expect(page.getByTestId('hero-placement')).toContainText(`Registered: ${sOwn}`);
  await expect(page.getByTestId('work-rows')).toContainText(bpatGpuH('mobility_le_8gpus'));
  await expect(page.locator('#map-main').getByText(`${bpatGpuH('mobility_le_8gpus')} GPU-h`)).toBeVisible();
  await btn(2).click();
  await expect(page.getByTestId('hero-nochange')).toBeVisible();
  await btn(3).click();
  await expect(page.getByTestId('work-rows')).toContainText(bpatGpuH('dest_slots_1024'));
  // the swap animates in at most 300 ms
  const dur = await page.getByTestId('work-rows').evaluate((el) => getComputedStyle(el).animationDuration);
  expect(parseFloat(dur) * (dur.endsWith('ms') ? 1 : 1000)).toBeLessThanOrEqual(300);
  await btn(0).click();
  await expect(page.getByTestId('hero-kind')).toContainText('registered result');
  // story 4 reads the same toggle state
  await btn(1).click();
  await page.goto('./#story-4');
  await expect(page.getByTestId('story-lock')).toContainText(`${sOwn} to ${sMobility}`);
  await page.locator('[data-step="4"]').evaluate((el) => el.scrollIntoView({ block: 'center' }));
  await expect(page.getByTestId('budget-story')).toBeVisible();
  await expect(page.getByTestId('story-work-rows')).toContainText(bpatGpuH('mobility_le_8gpus'));
});

test('reduced motion: the toggle swaps with no animation', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('./#control');
  await page.getByTestId('scenario-toggle').getByRole('button').nth(1).click();
  const name = await page.getByTestId('work-rows').evaluate((el) => getComputedStyle(el).animationName);
  expect(name).toBe('none');
});
