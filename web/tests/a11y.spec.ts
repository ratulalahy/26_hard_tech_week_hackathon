// axe-core scan (WCAG 2.0/2.1/2.2 A and AA) of every view and the method drawer, on the built dist/.
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const STATES = [
  { name: 'control', hash: '#control' },
  { name: 'cockpit', hash: '#cockpit' },
  { name: 'ribbon', hash: '#ribbon' },
  { name: 'story', hash: '#story' },
  { name: 'method', hash: '#control', drawer: true },
];

for (const s of STATES) {
  test(`axe ${s.name}`, async ({ page }) => {
    await page.goto('./' + s.hash);
    await page.locator('.mk-region').first().waitFor({ state: 'attached' });
    await page.waitForTimeout(800);
    if (s.drawer) { await page.getByRole('banner').getByRole('button', { name: 'Method & evidence' }).click(); await page.getByRole('dialog').waitFor(); }
    const r = await new AxeBuilder({ page }).withTags(TAGS).analyze();
    const summary = r.violations.map((v) => `${v.id} [${v.impact}] ×${v.nodes.length}: ${v.help} — ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`);
    console.log(`axe ${s.name}: ${r.violations.length} violations, ${r.passes.length} passes, ${r.incomplete.length} incomplete`);
    for (const line of summary) console.log('  ' + line);
    for (const v of r.incomplete) console.log(`  incomplete: ${v.id} ×${v.nodes.length} (${v.nodes.slice(0, 2).map((n) => n.target.join(' ')).join(' | ')})`);
    expect(summary).toEqual([]);
  });
}
