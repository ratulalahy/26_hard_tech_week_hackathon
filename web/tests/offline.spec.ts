// Offline acceptance (Task 8 Step 1): the built dist/, served on localhost, makes no request to any other
// host, and every view renders a value that comes from results/metrics.json.
import { expect, test, type Page } from '@playwright/test';
import { mobilityW, nRegister, waitW, weatherH, weatherS, caseExpect, waterCaveats, waterDays, waterExSpan, waterWithSpan, bpatGpuH, budgetHeadline, consumptionSpan, exact, fixtureManifest, placementRange, sMovedExec, sRemoteExec, testOwn, testPlacementRange, testWaitPhrase, lCommonSupport, sAbout, sMobility, sOwn, sOwnCI, sProduction, sTonnes, storageCombined, storageFlatT, storageHeadline, storageRushDays, storageRushN, testSOwn, testTimeOnlyRange, timeOnlyRange, uTonnes } from './expected';
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
  // T11/T13: the window switch shows the validation year by default; results/test now holds the one opening, so the test option is enabled
  await expect(page.getByRole('radio', { name: 'Validation year' })).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByRole('radio', { name: 'Test year (sealed, opened once)' })).toBeEnabled();
  await expect(page.getByTestId('window-switch')).toHaveAccessibleDescription('Validation year (Nov 2024 – Oct 2025) · test year sealed, opened once');
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
  // T17 (D-068): assumptions & what didn't work, from results/assumptions.json
  await expect(drawer.getByTestId('assumptions-register').locator('tbody tr')).toHaveCount(nRegister);
  await expect(drawer.getByTestId('assumptions-register')).toContainText(mobilityW);
  await expect(drawer.getByTestId('assumptions-negative')).toContainText(waitW);
  await expect(drawer.getByTestId('assumptions-negative')).toContainText('H3 not supported');
  await expect(drawer.getByTestId('assumptions-weather')).toContainText(weatherH);
  await expect(drawer.getByTestId('assumptions-weather')).toContainText(weatherS);
  await expect(drawer.getByTestId('assumptions-weather')).toContainText('even perfect carbon foresight does not beat a fixed ranking');

  await page.waitForLoadState('networkidle');
  expect(errors, 'page errors').toEqual([]);
  expect(g.blocked, 'blocked non-localhost requests').toEqual([]);
  const foreign = g.seen.filter((u) => /^(https?|wss?):/.test(u) && !LOCAL.has(new URL(u).hostname));
  expect(foreign, 'non-localhost requests attempted').toEqual([]);
  expect(g.seen.length).toBeGreaterThan(5);
});

/** r1 m3: data-valok exempts only a leaf that itself names the validation year. */
async function everyValokNamesValidation(loc: import('@playwright/test').Locator, where: string) {
  const bad = await loc.evaluate((el) => [...el.querySelectorAll('[data-valok]')].map((n) => n.textContent ?? '').filter((t) => !/validation/i.test(t)));
  expect(bad, `${where}: data-valok on an element that does not name the validation year`).toEqual([]);
}

/** The text of a region minus every element marked data-valok: the places that show a validation number in
 * test mode because the test year has no counterpart, each labelled as such (the drift table, val-only chips). */
async function unlabelledText(loc: import('@playwright/test').Locator) {
  return loc.evaluate((el) => {
    const c = el.cloneNode(true) as HTMLElement;
    c.querySelectorAll('[data-valok]').forEach((n) => n.remove());
    document.body.appendChild(c);
    const t = c.innerText;
    c.remove();
    return t;
  });
}

test('the test-year state shows only test numbers and no unlabelled validation wording (synthetic fixture)', async ({ page }) => {
  const g = guard(page);
  await g.install();
  await serveTestFixture(page);
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  const noValidation = async (where: string) => {
    for (const loc of [page.locator('main'), page.locator('footer')]) {
      const t = (await unlabelledText(loc)).toLowerCase();
      expect(t.split('\n').filter((l) => l.includes('validation')), `${where}: validation wording on test numbers`).toEqual([]);
      // M14: the test year covers a period, not a full year (checked on the unfiltered text)
      expect(/all year|over the year|the year's|whole year/.test((await loc.innerText()).toLowerCase()), `${where}: "year" wording on test numbers`).toBe(false);
      await everyValokNamesValidation(loc, where);
    }
  };

  await page.goto('./#control');
  await expect(page.getByTestId('hero-placement')).toContainText(sOwn);
  await openTestYear(page);
  await expect(page.getByRole('radio', { name: 'Test year (sealed, opened once)' })).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByTestId('hero-placement')).toContainText(exact(testSOwn)); // F10: S's own estimate
  if (testPlacementRange.includes('–')) await expect(page.locator('main')).not.toContainText(testPlacementRange);
  await expect(page.getByTestId('hero-timing')).toContainText(testWaitPhrase);
  await expect(page.getByTestId('scenario-toggle-off')).toContainText('no test counterpart');
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
  expect((await unlabelledText(drawer)).toLowerCase().includes('validation'), 'drawer: unlabelled validation wording').toBe(false);
  await page.keyboard.press('Escape');

  // back to the validation year: its numbers and wording return
  await page.getByRole('radio', { name: 'Validation year' }).click();
  await expect(page.getByTestId('story-result')).toContainText(sOwn);
  await expect(page.getByTestId('story-result')).toContainText('Over the validation year');

  await page.waitForLoadState('networkidle');
  expect(errors, 'page errors').toEqual([]);
  expect(g.blocked, 'blocked non-localhost requests').toEqual([]);
});

test('the ten-region overview page renders results/overview.json offline (T18)', async ({ page }) => {
  const { readFileSync } = await import('node:fs');
  const { join } = await import('node:path');
  const ov = JSON.parse(readFileSync(join(process.cwd(), 'public', 'data', 'results', 'overview.json'), 'utf8'));
  const g = guard(page);
  await g.install();
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto('./#regions');
  await expect(page.getByTestId('regions-table').locator('tbody tr')).toHaveCount(ov.order.length);
  // r1: every count follows the artifact's interval verdicts, never the sign of a point estimate
  const count = (f: (r: { alignment: { rush_verdict: string }; forecast: { ci: { skill: Record<string, { verdict: string }> } } }) => boolean) => ov.order.filter((b: string) => f(ov.regions[b])).length;
  const dirtier = count((r) => r.alignment.rush_verdict === 'dirtier');
  await expect(page.getByTestId('regions-title')).toContainText(`In ${dirtier} of ${ov.order.length} regions the net-load rush hours are dirtier`);
  const beatP = count((r) => r.forecast.ci.skill.vs_persistence.verdict === 'beats');
  const beatK = count((r) => r.forecast.ci.skill.vs_climatology.verdict === 'beats');
  await expect(page.getByTestId('regions-lede')).toContainText(`beats same-hour persistence in ${beatP} of ${ov.order.length} regions and the seasonal average (climatology) in ${beatK}`);
  // PACE vs climatology: shown greyed unless its interval clears zero (agrees with T19's outlook)
  const paceK = ov.regions.PACE.forecast.ci.skill.vs_climatology;
  const paceCell = page.getByTestId('regions-table').locator('tbody tr', { hasText: 'PACE' }).locator('[data-verdict]').nth(2);
  await expect(paceCell).toHaveAttribute('data-verdict', paceK.verdict);
  // the default ranking is by daily swing: the first row is the widest swing
  const widest = [...ov.order].sort((a: string, b: string) => ov.regions[b].swing.median_g.value - ov.regions[a].swing.median_g.value)[0];
  await expect(page.getByTestId('regions-table').locator('tbody tr').first()).toContainText(widest);
  await expect(page.getByTestId('regions-sources')).toContainText('test year sealed');
  await expect(page.locator('canvas.maplibregl-canvas')).toBeVisible();
  await expect(page.locator('.mk-ov')).toHaveCount(ov.order.length);
  // selecting a row drives the detail panel
  await page.getByTestId('regions-table').getByRole('button', { name: /PJM/ }).click();
  await expect(page.getByTestId('regions-detail')).toContainText('PJM Interconnection · PJM');
  // and the page hands back to the App shell
  await page.getByRole('link', { name: 'Back to the Utah dashboard' }).click();
  await expect(page.getByTestId('hero-placement')).toContainText(sOwn); // the hero leads with S's own estimate (T15, F10)
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

test('the sealed test year (results/test, opened once): extras, storage, drift; no "pending" phases', async ({ page }) => {
  const { readFileSync } = await import('node:fs');
  const { join } = await import('node:path');
  const rd = (f: string) => JSON.parse(readFileSync(join(process.cwd(), 'public', 'data', 'results', 'test', f), 'utf8'));
  const m = rd('metrics.json'), x = rd('extras.json');
  const f1 = (v: number) => (v * 100).toFixed(1);
  const cs = (c: string, ref = 'U') => m.contrasts.find((y: { candidate: string; reference: string }) => y.candidate === c && y.reference === ref).blocks['4'];
  const sU = cs('S');
  const kS = cs('K', 'S');
  const peak = x.storage.schedule_comparison.schedules.peak.cases.U['4'];
  const mob = ['S', 'W', 'L'].map((p) => x.extensions.mobility_le_8gpus.vs_U[p]['4'].saving.value as number);
  const g = guard(page);
  await g.install();
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto('./#control');
  await openTestYear(page);
  await expect(page.getByRole('radio', { name: 'Test year (sealed, opened once)' })).toHaveAttribute('aria-checked', 'true');
  // the registered b = 4 S interval, read from the JSON
  await expect(page.getByTestId('hero-placement')).toContainText(`${f1(sU.saving.value)}%`);
  await expect(page.getByTestId('hero-placement')).toContainText(`${f1(sU.saving_ci95.value[0])}–${f1(sU.saving_ci95.value[1])}%`);
  await expect(page.getByTestId('hero-kind')).toContainText('test year (sealed, opened once)');
  await expect(page.getByTestId('hero-mobility')).toContainText(`${f1(Math.min(...mob))}–${f1(Math.max(...mob))}%`);

  await page.goto('./#story-3');
  await expect(page.getByTestId('story-h3')).toContainText('H3 not supported');
  await expect(page.getByTestId('story-h3')).toContainText(`K emitted ${(-kS.diff_kg.value / 1000).toFixed(1)} t more than S (95% interval ${(-kS.diff_kg_ci95.value[1] / 1000).toFixed(1)} to ${(-kS.diff_kg_ci95.value[0] / 1000).toFixed(1)} t, excludes zero)`);
  await expect(page.getByTestId('story-result')).toContainText(`${(cs('W_time').saving.value * 100).toFixed(2)}%`);
  await expect(page.getByTestId('story-storage-test')).toContainText(`${peak.rush_import_after_mw.value.toFixed(2)} MW`);
  await expect(page.getByTestId('story-storage-test')).toContainText(`${peak.rush_hours_discharging.value} of ${x.storage.rush.n_hours.value} rush hours`);
  // r1 M2: the flat-marginal skeptic line, read from the JSON (negative cut = adds CO₂)
  const carbonFlat = -x.storage.schedule_comparison.schedules.carbon.cases.U['4'].flat_marginal_cut_t.value as number;
  const peakFlat = -peak.flat_marginal_cut_t.value as number;
  await expect(page.getByTestId('storage-skeptic-test')).toContainText(`add about ${Math.round(carbonFlat)} t on the carbon schedule and ${Math.round(peakFlat)} t aimed at the peak`);
  // r1 m1: an average draw over the rush hours, and the yearly peak draw does not fall
  await expect(page.getByTestId('story-storage-test')).toContainText("cluster's average draw");
  await expect(page.getByTestId('story-storage-test')).toContainText(`(${peak.peak_import_before_mw.value.toFixed(2)} → ${peak.peak_import_after_mw.value.toFixed(2)} MW)`);
  await page.goto('./#story-5');
  await expect(page.getByTestId('story-storage-skeptic-panel')).toContainText(`${Math.round(peakFlat)} t`);
  // r1 M1: beat 4's map is the test year's replay week, titled from S's own test estimate; only the toggle is validation-only
  await page.goto('./#story-4');
  await expect(page.getByTestId('story-map-title')).toContainText(`S static clean-region ranking: ${f1(sU.saving.value)}% less CO₂`);
  await expect(page.getByTestId('story-map-title')).toContainText('test year (sealed, opened once)');
  await expect(page.locator('main')).not.toContainText('saving not run');
  await expect(page.getByTestId('scenario-toggle-off')).toContainText("The map shows the test year's own replay week");
  await expect(page.locator('main')).not.toContainText(/pending/i);

  await page.getByRole('navigation', { name: 'Views' }).getByRole('link', { name: 'Day ribbon' }).click();
  await expect(page.getByTestId('test-tough-days').locator('tbody tr')).toHaveCount(x.toughest_days.days.length);

  await page.getByRole('banner').getByRole('button', { name: 'Method & evidence' }).click();
  const drawer = page.getByRole('dialog');
  await expect(drawer.getByTestId('drift-view')).toBeVisible();
  await expect(drawer.getByTestId('drift-table').locator('tbody tr')).toHaveCount(x.drift.rows.filter((r: { item: string }) => r.item === 'headline').length);
  await drawer.getByTestId('drift-item').selectOption('5 seasonal');
  await expect(drawer.getByTestId('drift-table').locator('tbody tr')).toHaveCount(x.drift.rows.filter((r: { item: string }) => r.item === '5 seasonal').length);
  await expect(drawer.getByTestId('method-storage-test')).toContainText(`${peak.rush_import_after_mw.value.toFixed(2)}`);
  await expect(drawer.getByTestId('test-item-6-permutation-importance')).toBeVisible();
  await expect(drawer.getByTestId('test-item-6-forecast-skill')).toBeVisible();
  await expect(drawer.getByTestId('method-h3')).toContainText('H3 not supported');
  // r1 m6: the frozen intervals' coverage on the test year, from the JSON
  const covs = Object.values(x.forecast_skill.series as Record<string, Record<string, { models: Record<string, { interval: { coverage: { value: number } } }> }>>)
    .flatMap((ts) => Object.values(ts).flatMap((t) => Object.values(t.models ?? {}).map((mm) => mm.interval?.coverage?.value).filter((c): c is number => typeof c === 'number')));
  await expect(drawer.getByTestId('method-coverage')).toContainText(`covered ${Math.round(Math.min(...covs) * 100)}–${Math.round(Math.max(...covs) * 100)}% of hours (nominal 80%)`);
  // r1 m2: rush rows read "a of N" per year, with no difference cell
  await drawer.getByTestId('drift-item').selectOption('2b storage schedules');
  const peakRow = drawer.getByTestId('drift-table').locator('tbody tr').filter({ hasText: /^peak schedule, U, 4 MWh: rush hours discharging/ });
  await expect(peakRow.locator('td').nth(1)).toHaveText('4 of 12');
  await expect(peakRow.locator('td').nth(2)).toHaveText(`${peak.rush_hours_discharging.value} of ${x.storage.rush.n_hours.value}`);
  await expect(peakRow.locator('td').nth(3)).toHaveText('');
  await expect(drawer.getByTestId('drift-view').getByTestId('rush-caption')).toContainText('different hours: 12 in validation, 14 in test');
  await everyValokNamesValidation(drawer, 'drawer');
  expect(/all year|over the year|the year's|whole year/.test((await drawer.innerText()).toLowerCase()), 'drawer: "year" wording').toBe(false);
  // the manifest's two pre-extras caveats are restated: phases 49 and 98 ran, shadow-U was cut (never "pending")
  await expect(drawer).not.toContainText(/pending/i);
  await expect(drawer).toContainText('offsets of 49 and 98 days ran on the test year');
  await expect(drawer).toContainText('cut by owner (D-058)');
  const lines = (await unlabelledText(drawer)).split('\n').filter((l) => /validation/i.test(l));
  expect(lines, 'drawer: unlabelled validation wording').toEqual([]);
  await page.waitForLoadState('networkidle');
  expect(errors, 'page errors').toEqual([]);
  expect(g.blocked, 'blocked non-localhost requests').toEqual([]);
});
