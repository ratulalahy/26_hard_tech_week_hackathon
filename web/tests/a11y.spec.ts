// axe-core scan (WCAG 2.0/2.1/2.2 A and AA) of every view and the method drawer, on the built dist/.
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { openTestYear, serveTestFixture } from './fixture-route';

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const STATES: { name: string; hash: string; drawer?: boolean; testYear?: boolean; real?: boolean; toggle?: number; width?: number }[] = [
  { name: 'control', hash: '#control' },
  { name: 'cockpit', hash: '#cockpit' },
  { name: 'ribbon', hash: '#ribbon' },
  { name: 'story', hash: '#story' },
  { name: 'story-4', hash: '#story-4' }, // T15: the toggle, the scenario map and the flexibility budget
  { name: 'story-5', hash: '#story-5' }, // T10b: the storage beat (F18), beat 5 in the D-064 order
  { name: 'story-6', hash: '#story-6' }, // the evidence
  { name: 'control-mobility', hash: '#control', toggle: 1 }, // T15: a scenario estimate on the control room
  { name: 'outlook', hash: '#outlook' }, // T19: the grid outlook page
  { name: 'prices', hash: '#prices' }, // T22: the price lens page
  { name: 'method', hash: '#control', drawer: true },
  { name: 'test-year control', hash: '#control', testYear: true },
  { name: 'test-year method', hash: '#control', testYear: true, drawer: true },
  { name: 'method-390', hash: '#control', drawer: true, width: 390 }, // T17: phone-width drawer
  // the sealed test year as committed (results/test, opened once): extras, storage, toughest days, drift
  { name: 'sealed control', hash: '#control', testYear: true, real: true },
  { name: 'sealed ribbon', hash: '#ribbon', testYear: true, real: true },
  { name: 'sealed story-5', hash: '#story-5', testYear: true, real: true },
  { name: 'sealed method', hash: '#control', testYear: true, real: true, drawer: true },
];

for (const s of STATES) {
  test(`axe ${s.name}`, async ({ page }) => {
    if (s.testYear && !s.real) await serveTestFixture(page);
    if (s.width) await page.setViewportSize({ width: s.width, height: 844 });
    await page.goto('./' + s.hash);
    await page.locator('.mk-region').first().waitFor({ state: 'attached' });
    if (s.testYear) { await openTestYear(page); await page.locator('.mk-region').first().waitFor({ state: 'attached' }); }
    await page.waitForTimeout(800);
    // a story beat is dimmed until it is the step in view; after the window switch remounts the story, wait for it
    const beat = /^#story-(\d)$/.exec(s.hash);
    if (beat) await expect(page.locator(`#story-${beat[1]} > section`).first()).toHaveCSS('opacity', '1');
    if ('toggle' in s && s.toggle) { await page.getByTestId('scenario-toggle').getByRole('button').nth(s.toggle).click(); await page.waitForTimeout(400); }
    if (s.drawer) {
      // at phone width the banner button can sit outside the viewport, so it is clicked in the DOM
      await page.getByRole('banner').getByRole('button', { name: 'Method & evidence' }).evaluate((b: HTMLButtonElement) => b.click());
      await page.getByRole('dialog').waitFor();
    }
    if (s.width) {
      // T17 smoke: the register stacks with per-cell labels, and the drawer does not scroll sideways
      const reg = page.getByTestId('assumptions-register');
      await reg.scrollIntoViewIfNeeded();
      await expect(reg).toBeVisible();
      const label = await reg.locator('td[data-label="How reality differs"]').first().evaluate((el) => getComputedStyle(el, '::before').content);
      expect(label).toBe('"How reality differs"');
      const [sw, cw] = await page.getByRole('region', { name: 'Method and evidence details' }).evaluate((el) => [el.scrollWidth, el.clientWidth]);
      expect(sw).toBeLessThanOrEqual(cw + 1);
    }
    const r = await new AxeBuilder({ page }).withTags(TAGS).analyze();
    const summary = r.violations.map((v) => `${v.id} [${v.impact}] ×${v.nodes.length}: ${v.help} — ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`);
    console.log(`axe ${s.name}: ${r.violations.length} violations, ${r.passes.length} passes, ${r.incomplete.length} incomplete`);
    for (const line of summary) console.log('  ' + line);
    for (const v of r.incomplete) console.log(`  incomplete: ${v.id} ×${v.nodes.length} (${v.nodes.slice(0, 2).map((n) => n.target.join(' ')).join(' | ')})`);
    expect(summary).toEqual([]);
  });
}

// T18: the standalone ten-region overview page (#regions), with its map labels drawn and a row selected.
test('axe regions', async ({ page }) => {
  await page.goto('./#regions');
  await page.getByTestId('regions-table').waitFor();
  await page.locator('.mk-ov').first().waitFor({ state: 'attached' });
  await page.getByRole('button', { name: /^\d+\s*CISO/ }).click();
  await page.waitForTimeout(800);
  const r = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const summary = r.violations.map((v) => `${v.id} [${v.impact}] ×${v.nodes.length}: ${v.help} — ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`);
  console.log(`axe regions: ${r.violations.length} violations, ${r.passes.length} passes, ${r.incomplete.length} incomplete`);
  for (const line of summary) console.log('  ' + line);
  expect(summary).toEqual([]);
});

// T21: every page of the nav shell at 1440 and 390 px, the top bar included (0 violations).
const T21: { name: string; hash: string; ready: string }[] = [
  { name: 'story', hash: '#control', ready: '.mk-region' },
  { name: 'story-beat', hash: '#story-3', ready: '.mk-region' },
  { name: 'monitor', hash: '#monitor', ready: '[data-testid="monitor-feed"] li' },
  { name: 'outlook', hash: '#outlook', ready: '[data-testid="outlook-days"] li' },
  { name: 'regions', hash: '#regions', ready: '.mk-ov' },
  { name: 'prices', hash: '#prices', ready: '[data-testid="prices-title"]' },
  { name: 'evidence', hash: '#evidence', ready: '[data-testid="assumptions-register"]' },
];
for (const w of [1440, 390]) {
  for (const s of T21) {
    test(`axe t21 ${s.name} ${w}`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: w === 390 ? 844 : 900 });
      await page.goto('./' + s.hash);
      await page.locator(s.ready).first().waitFor({ state: 'attached' });
      await page.waitForTimeout(800);
      const r = await new AxeBuilder({ page }).withTags(TAGS).analyze();
      const summary = r.violations.map((v) => `${v.id} [${v.impact}] ×${v.nodes.length}: ${v.help} — ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`);
      console.log(`axe t21 ${s.name} ${w}: ${r.violations.length} violations, ${r.passes.length} passes, ${r.incomplete.length} incomplete`);
      for (const line of summary) console.log('  ' + line);
      expect(summary).toEqual([]);
    });
  }
}
