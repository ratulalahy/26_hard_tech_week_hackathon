// Offline acceptance (Task 8 Step 1): the built dist/, served on localhost, makes no request to any other
// host, and every view renders a value that comes from results/metrics.json.
import { expect, test, type Page } from '@playwright/test';
import { caseExpect, waterCaveats, waterDays, waterExSpan, waterWithSpan, bpatGpuH, budgetHeadline, consumptionSpan, exact, fixtureManifest, placementRange, sMovedExec, sRemoteExec, testOwn, testPlacementRange, testWaitPhrase, lCommonSupport, sAbout, sMobility, sOwn, sOwnCI, sProduction, sTonnes, storageCombined, storageFlatT, storageHeadline, storageRushDays, storageRushN, testSOwn, testTimeOnlyRange, timeOnlyRange, uTonnes } from './expected';
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
  await expect(hero).toContainText(exact(sOwn));
  await expect(hero).toContainText(`Its own 95% interval ${sOwnCI}`);
  if (placementRange.includes('–')) await expect(page.locator('main')).not.toContainText(placementRange); // I7: never the span
  await expect(page.getByTestId('hero-kind')).toContainText('registered result');
  await expect(page.getByTestId('hero-timing')).toContainText('under 1%');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(`In a simulated replay, moving Utah's AI jobs cut their attributed CO₂ by about ${sAbout}%; waiting in Utah cut under 1%.`);
  await expect(page.getByTestId('hero-frame')).toHaveText('Replay of a measured GPU-cluster trace mapped onto Utah · deadlines relative to the baseline, met by construction · exact declared runtimes; runtime uncertainty untested.');
  await expect(hero).toContainText('deadlines met by construction (baseline bookings)');
  await expect(page.getByTestId('hero-mobility')).toContainText(`${sOwn} → ${sMobility} if only jobs of 8 GPUs or fewer may move`);
  await expect(page.getByTestId('budget-headline').first()).toHaveText(budgetHeadline);
  await expect(page.getByTestId('budget-title')).toHaveText('Flexibility budget (registered run): S static clean-region ranking');
  // I1: the remote line is on the execution basis, and remote + retimed + slips = the ledger's moved
  await expect(page.getByTestId('remote-line')).toContainText(`by execution energy, S static clean-region ranking ran ${sRemoteExec} outside Utah`);
  await expect(page.getByTestId('remote-line')).toContainText(`for the ledger's “moved” ${sMovedExec}`);
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
  await expect(page.getByTestId('ribbon-own-W_time')).toContainText('W wait-only'); // M9: each policy's own estimate
  await expect(page.getByTestId('forecast-chart')).toBeVisible();
  await expect(page.getByText('retrospective ±week MAE; not a prediction interval').first()).toBeVisible();
  // T16 (D-066): the toughest-days card, one pre-registered day at a time
  const days = page.getByRole('radiogroup', { name: 'Toughest days' }).getByRole('radio');
  await expect(days).toHaveCount(3);
  for (const [i, e] of caseExpect.entries()) {
    await expect(days.nth(i)).toHaveText(e.button);
    await days.nth(i).click();
    await expect(days.nth(i)).toHaveAttribute('aria-checked', 'true');
    await expect(page.getByTestId('case-story')).toContainText(e.rank);
    await expect(page.getByTestId('case-story')).toContainText(e.cluster);
    await expect(page.getByTestId('case-temp')).toContainText(e.peak);
    await expect(page.getByTestId('case-temp')).toContainText(e.slc);
    await expect(page.getByTestId('case-context')).toContainText('Context, not evidence');
    await expect(page.getByTestId('case-context')).toContainText(e.context);
    await expect(page.getByTestId('case-chart')).toBeVisible();
    // fix round 1: totals include transfer; "by day" is explained; the scale note; SLC only
    await expect(page.getByTestId('case-days').locator('..')).toContainText('CO₂ incl. transfer, by day');
    await expect(page.getByTestId('case-note')).toContainText('CO₂ counted in the hour the job ran, transfer at arrival; a job spanning midnight is split between days. Not comparable to the annual saving.');
    await expect(page.getByTestId('case-note')).toContainText(e.scale);
    await expect(page.getByTestId('case-temp')).toContainText('Salt Lake City only');
    if (e.small) await expect(page.getByTestId('case-note')).toContainText("This day's Utah workload was about half");
    // every cited source is fully visible (no clamp)
    for (const a of await page.getByTestId('case-context').getByRole('link').all()) await expect(a).toBeInViewport({ ratio: 1 });
  }

  await page.goto('./#story');
  await expect(page.getByTestId('story-result')).toContainText(exact(sOwn));
  await expect(page.getByTestId('story-result')).toContainText('no demonstrated aggregate benefit from dynamic search in this replay');
  await expect(page.getByTestId('story-result')).not.toContainText('vs under 1%'); // M5: said once
  // T10b (F18, fix r1): story 5 (D-064 order) is the storage illustration, from results/storage.json
  await page.goto('./#story-5');
  await expect(page.getByTestId('storage-headline')).toContainText(storageHeadline);
  await expect(page.getByTestId('storage-combined')).toContainText(storageCombined);
  await expect(page.getByTestId('storage-skeptic')).toContainText(`On a flat marginal basis it may add about ${storageFlatT} t: storage only helps if charging carbon ÷ η < displaced carbon.`);
  await expect(page.getByTestId('storage-curve')).toBeVisible();
  await expect(page.getByTestId('storage-import')).toBeVisible();
  await expect(page.getByText('illustrative · not the registered result')).toBeVisible();
  // T14: one water line in story 5 (the storage beat, D-064 order), from results/water.json
  await expect(page.getByTestId('story-water')).toContainText(`Moving work also shifts its water footprint: ${waterExSpan} million gallons over the ${waterDays}-day validation window on the fuel mix alone, but ${waterWithSpan} million if hydro reservoir evaporation is counted (illustrative).`);
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
  // T14: the water panel, with Astra's caveats verbatim
  await expect(drawer.getByTestId('method-water')).toContainText(`${waterExSpan} million gallons`);
  await expect(drawer.getByTestId('water-table')).toContainText('W weekly profile');
  await expect(drawer.getByTestId('water-sites')).toContainText('Northwest hydro');
  for (const c of waterCaveats) await expect(drawer.getByTestId('water-caveats')).toContainText(c);

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
  await expect(page.getByTestId('hero-placement')).toContainText(exact(testSOwn)); // F10: S's own estimate
  if (testPlacementRange.includes('–')) await expect(page.locator('main')).not.toContainText(testPlacementRange);
  await expect(page.getByTestId('hero-timing')).toContainText(testWaitPhrase);
  await expect(page.getByTestId('scenario-toggle-off')).toHaveText('The mobility and capacity scenarios are not shown for this window.');
  await expect(page.getByRole('heading', { level: 1 })).toContainText(`moving Utah's AI jobs cut their CO₂ by ${testSOwn}`);
  await expect(page.getByTestId('window-switch')).toHaveAccessibleDescription(/^Test year \(Nov 2025 – Oct 2026\) · opened once, after the freeze of Oct 27, 2026$/);
  await noValidation('control');

  for (const [tab, id, want] of [['Decision cockpit', 'cockpit-registered', testSOwn], ['Day ribbon', 'ribbon-own-W_time', testOwn('W_time')], ['Story', 'story-result', testSOwn]] as const) {
    await page.getByRole('navigation', { name: 'Views' }).getByRole('link', { name: tab }).click();
    await expect(page.getByTestId(id)).toContainText(want);
    await noValidation(tab);
  }
  await expect(page.getByTestId('story-result')).toContainText('Over the test year');
  // M1: story 4 in the test window falls back to the policy's own test estimate, with window copy
  await expect(page.getByTestId('story-lock-own')).toContainText(`Over the test year, S static clean-region ranking cut attributed CO₂ by ${testSOwn}`);
  await expect(page.getByTestId('story-lock-own')).toContainText('not shown for this window');

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
  await expect(page.getByTestId('budget-toggle-note')).toHaveText('The toggle does not change this bar.'); // I4
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
  await expect(page.getByTestId('story-lock')).toContainText(`falls from ${sOwn} to ${sMobility}`);
  await page.locator('[data-step="4"]').evaluate((el) => el.scrollIntoView({ block: 'center' }));
  await expect(page.getByTestId('budget-story')).toBeVisible();
  await expect(page.getByTestId('story-work-rows')).toContainText(bpatGpuH('mobility_le_8gpus'));
  await expect(page.getByTestId('story-budget-toggle-note')).toBeVisible(); // I4
  // I5: story 4 shows S's no-change note in the wait-only state
  await page.getByTestId('scenario-toggle').getByRole('button').nth(2).click();
  await expect(page.getByTestId('story-nochange')).toBeVisible();
});

test('reduced motion: the toggle swaps with no animation', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('./#control');
  await page.getByTestId('scenario-toggle').getByRole('button').nth(1).click();
  const name = await page.getByTestId('work-rows').evaluate((el) => getComputedStyle(el).animationName);
  expect(name).toBe('none');
});
