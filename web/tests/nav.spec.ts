// T21: the nav shell and the Monitor page, on the built dist/. Every route renders offline; the pitch's deep
// links (#story-1…5, #control) land where they did before the shell; the nav is keyboard-operable; the year
// switch shows only where it applies; the Monitor replays committed test outputs with template-only reasons.
import { readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';

const LOCAL = new Set(['127.0.0.1', 'localhost', '[::1]']);
const testJob = JSON.parse(readFileSync(new URL('../public/data/results/test/job-replay.json', import.meta.url), 'utf8'));
const testMan = JSON.parse(readFileSync(new URL('../public/data/results/test/manifest.json', import.meta.url), 'utf8'));

async function offline(page: Page) {
  const blocked: string[] = [], errors: string[] = [];
  await page.context().route('**/*', (route) => {
    const u = new URL(route.request().url());
    if ((u.protocol === 'http:' || u.protocol === 'https:' || u.protocol === 'ws:' || u.protocol === 'wss:') && !LOCAL.has(u.hostname)) { blocked.push(u.href); return route.abort('blockedbyclient'); }
    return route.continue();
  });
  page.on('pageerror', (e) => errors.push(String(e)));
  return { blocked, errors };
}
const pages = (page: Page) => page.getByRole('navigation', { name: 'Pages' });

const ROUTES: { hash: string; page: string; ready: string; windowSwitch: boolean; views: boolean }[] = [
  { hash: '#control', page: 'Story', ready: '[data-testid="hero-placement"]', windowSwitch: true, views: true },
  { hash: '', page: 'Story', ready: '[data-testid="hero-placement"]', windowSwitch: true, views: true }, // the default page
  { hash: '#monitor', page: 'Monitor', ready: '[data-testid="monitor-feed"] li', windowSwitch: false, views: false },
  { hash: '#outlook', page: 'Outlook', ready: '[data-testid="outlook-title"]', windowSwitch: false, views: false },
  { hash: '#regions', page: 'Regions', ready: '[data-testid="regions-table"]', windowSwitch: false, views: false },
  { hash: '#prices', page: 'Prices', ready: '[data-testid="prices-title"]', windowSwitch: false, views: false },
  { hash: '#evidence', page: 'Evidence', ready: '[data-testid="assumptions-register"]', windowSwitch: true, views: false },
];

for (const r of ROUTES) {
  test(`route ${r.hash || '(none)'} renders offline with the shell`, async ({ page }) => {
    const g = await offline(page);
    await page.goto('./' + r.hash);
    await expect(page.locator(r.ready).first()).toBeVisible();
    await expect(page.getByRole('banner')).toHaveCount(1); // one top bar on every page
    await expect(pages(page).getByRole('link', { name: r.page })).toHaveAttribute('aria-current', 'page');
    await expect(pages(page).locator('[aria-current="page"]')).toHaveCount(1);
    await expect(page.getByTestId('window-switch')).toHaveCount(r.windowSwitch ? 1 : 0);
    await expect(page.getByRole('navigation', { name: 'Views' })).toHaveCount(r.views ? 1 : 0);
    await page.waitForLoadState('networkidle');
    expect(g.errors, 'page errors').toEqual([]);
    expect(g.blocked, 'blocked non-localhost requests').toEqual([]);
  });
}

test('the pitch deep links land where they did: #story-1…5 and #control', async ({ page }) => {
  for (const n of [1, 2, 3, 4, 5]) {
    await page.goto(`./#story-${n}`);
    const beat = page.locator(`#story-${n} > section`).first();
    await expect(beat).toHaveCSS('opacity', '1'); // the beat in view is the one the hash names
    await expect(beat).toBeInViewport();
    await expect(pages(page).getByRole('link', { name: 'Story' })).toHaveAttribute('aria-current', 'page');
    await expect(page.getByRole('navigation', { name: 'Views' }).getByRole('link', { name: 'Story' })).toHaveAttribute('aria-current', 'page');
  }
  await page.goto('./#control');
  await expect(page.getByTestId('hero-placement')).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Views' }).getByRole('link', { name: 'Control room' })).toHaveAttribute('aria-current', 'page');
  // the deep links also land from another page, without a reload (hash change only)
  await page.goto('./#monitor');
  await page.getByTestId('monitor-feed').waitFor();
  await page.evaluate(() => { location.hash = '#story-3'; });
  await expect(page.locator('#story-3 > section').first()).toHaveCSS('opacity', '1');
  await expect(page.locator('#story-3 > section').first()).toBeInViewport();
  await page.evaluate(() => { location.hash = '#story-5'; });
  await expect(page.locator('#story-5 > section').first()).toHaveCSS('opacity', '1');
  await page.evaluate(() => { location.hash = '#control'; });
  await expect(page.getByTestId('hero-placement')).toBeVisible();
});

test('the nav is keyboard-operable and the Story tab returns to the last view', async ({ page }) => {
  await page.goto('./#ribbon');
  await page.getByTestId('forecast-chart').waitFor();
  const monitor = pages(page).getByRole('link', { name: 'Monitor' });
  await monitor.focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#monitor$/);
  await expect(page.getByTestId('monitor-title')).toBeVisible();
  await page.keyboard.press('Shift+Tab'); // back along the nav: Story is before Monitor
  await expect(pages(page).getByRole('link', { name: 'Story' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#ribbon$/);
  await expect(page.getByTestId('forecast-chart')).toBeVisible();
});

test('the year switch changes the Evidence page; the method drawer stays on Story', async ({ page }) => {
  await page.goto('./#evidence');
  await expect(page.getByTestId('evidence-drift-hint')).toBeVisible();
  await expect(page.getByRole('banner').getByRole('button', { name: 'Method & evidence' })).toHaveCount(0);
  await page.getByRole('radio', { name: /^Test year/ }).click();
  await expect(page.getByTestId('evidence')).toContainText('Validation → test drift');
  await page.goto('./#control');
  await page.getByRole('banner').getByRole('button', { name: 'Method & evidence' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.evaluate(() => { location.hash = '#prices'; }); // leaving the Story page closes the drawer
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('the Monitor replays committed test outputs: label, playback, template reasons', async ({ page }) => {
  const g = await offline(page);
  await page.goto('./#monitor');
  const feed = page.getByTestId('monitor-feed');
  await expect(feed.locator('li').first()).toBeVisible();
  await expect(page.getByTestId('monitor-label')).toHaveText('simulated replay · test year (sealed, opened once)');
  // the title's counts are the S arcs of results/test/job-replay.json
  const moved = testJob.week.policies.S.arcs.reduce((a: number, x: { jobs: { value: number } }) => a + x.jobs.value, 0);
  await expect(page.getByTestId('monitor-title')).toContainText(`S sent ${moved} of`);
  // the frozen ranking, as the S rule states it, comes from the test manifest
  const order: string[] = testMan.s_ranking.order;
  const ranking = order.map((s) => `${s} ${Math.round(testMan.s_ranking.mean_consumed_ci[s].value)}`).join(' < ');
  await expect(feed).toContainText(`S rule: first feasible site in the frozen ranking (${ranking} g/kWh)`);
  // scrub, step and play
  const clock = page.getByTestId('monitor-clock');
  const scrub = page.getByTestId('monitor-scrub');
  await scrub.fill('0');
  await expect(feed.locator('li')).toHaveCount(1); // only the week's opening line at hour 1
  await scrub.focus();
  await page.keyboard.press('End');
  await expect(clock).toContainText('hour 168 of 168');
  const all = await feed.locator('li').count();
  await page.getByRole('button', { name: 'Previous feed entry' }).click();
  await expect.poll(() => feed.locator('li').count()).toBeLessThan(all);
  await scrub.fill('0');
  await page.getByRole('radio', { name: '24 h/s' }).click();
  await page.getByRole('button', { name: 'Play replay' }).click();
  await expect(clock).not.toContainText('hour 1 of 168');
  await page.getByRole('button', { name: 'Pause replay' }).click();
  // every comparison of outcomes is labelled retrospective
  for (const id of ['monitor-rate', 'monitor-week']) await expect(page.getByTestId(id)).toContainText('retrospective, scored on realized truth');
  const traced = page.getByTestId('monitor-traced-feed');
  await expect(traced.locator('li')).toHaveCount(2);
  await expect(traced).toContainText(`Job ${testJob.illustrative_job.job_uid}`);
  await expect(traced).toContainText('Retrospective, scored on realized truth');
  expect(g.errors).toEqual([]);
  expect(g.blocked).toEqual([]);
});

test('the Monitor never says S forecast or predicted, or chose the lowest actual emissions', async ({ page }) => {
  await page.goto('./#monitor');
  await page.getByTestId('monitor-feed').locator('li').first().waitFor();
  await page.getByTestId('monitor-scrub').fill(String(testJob.week.hours.length - 1)); // every entry shown
  const text = [await page.getByTestId('monitor-feed').innerText(), await page.getByTestId('monitor-traced-feed').innerText()].join('\n');
  expect(text.length).toBeGreaterThan(200);
  expect(text).not.toMatch(/forecast|predict/i);
  expect(text).not.toMatch(/lowest[- ]?(actual|real|realized)?[- ]?(co2|co₂|carbon|emission)/i);
  const body = await page.getByTestId('monitor').innerText();
  expect(body).not.toMatch(/predict/i);
  expect(body).not.toMatch(/S (forecast|chose the lowest)/i);
});

// Lead addition: the pitch deck opens deep links in one window; ?year=test starts in the sealed test year, and
// the year last chosen is remembered. A fresh visitor with no parameter still starts in the validation year.
const yearChecked = (page: Page, name: RegExp) => expect(page.getByRole('radio', { name }).and(page.locator('[aria-checked="true"]'))).toHaveCount(1);

test('?year=test opens a deep link in the test year; a fresh visit stays on validation', async ({ page }) => {
  await page.goto('./?year=test#story-3');
  await yearChecked(page, /^Test year/);
  await expect(page.locator('#story-3 > section').first()).toHaveCSS('opacity', '1');
  await expect(page.getByTestId('window-switch')).toHaveAccessibleDescription(/^Test year/);
  await page.goto('./?year=test#control');
  await yearChecked(page, /^Test year/);
  await expect(page.getByTestId('hero-placement')).toBeVisible();
  await page.evaluate(() => localStorage.clear());
  await page.goto('./#control');
  await yearChecked(page, /^Validation year/);
});

test('the year last chosen is remembered; ?year=validation overrides it', async ({ page }) => {
  await page.goto('./#control');
  await yearChecked(page, /^Validation year/);
  await page.getByRole('radio', { name: /^Test year/ }).click();
  await yearChecked(page, /^Test year/);
  await page.goto('./#story-2');
  await page.reload();
  await yearChecked(page, /^Test year/);
  await expect(page.locator('#story-2 > section').first()).toHaveCSS('opacity', '1');
  await page.goto('./?year=validation#control');
  await yearChecked(page, /^Validation year/);
  await page.goto('./#control'); // the override is itself remembered
  await yearChecked(page, /^Validation year/);
});

test('blocked storage falls back to validation without errors; ?year=test still works', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { get() { throw new Error('storage blocked'); } });
  });
  await page.goto('./#control');
  await yearChecked(page, /^Validation year/);
  await page.getByRole('radio', { name: /^Test year/ }).click();
  await yearChecked(page, /^Test year/);
  await page.goto('./?year=test#story-1');
  await yearChecked(page, /^Test year/);
  expect(errors).toEqual([]);
});
