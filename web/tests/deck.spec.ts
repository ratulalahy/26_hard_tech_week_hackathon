// The offline pitch deck (docs/pitch/deck/index.html): opened from file:// with every network request
// blocked, it steps through every slide with no console error, keeps every slide inside its 16:9 stage
// at the two presentation sizes, shows only numbers that match data.js (built from results/), and
// links each beat slide to its dashboard deep link. DECK_SHOTS=1 also writes
// docs/design/shots-build/deck-<label>-<width>.png.
import { expect, test, type Page } from '@playwright/test';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

const deck = resolve(here, '../../docs/pitch/deck/index.html');
const shots = resolve(here, '../../docs/design/shots-build');
const URL0 = pathToFileURL(deck).href;
const LINKS: Record<string, string> = { '2': '#story-1', '4': '#story-2', '5': '#story-3', '6': '#story-4', '7': '#story-5', '8': '#control' };

async function open(page: Page) {
  const errors: string[] = [];
  const net: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`${m.type()}: ${m.text()}`); });
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.context().route('**/*', (route) => {
    const u = route.request().url();
    if (u.startsWith('file://')) return route.continue();
    net.push(u);
    return route.abort('internetdisconnected');
  });
  await page.goto(URL0);
  await expect(page.locator('html')).toHaveAttribute('data-ready', '1');
  await page.evaluate(() => document.fonts.ready);
  return { errors, net };
}

for (const vp of [{ width: 1728, height: 1117 }, { width: 1440, height: 900 }]) {
  test(`deck steps through every slide offline at ${vp.width}×${vp.height}`, async ({ page }) => {
    await page.setViewportSize(vp);
    const { errors, net } = await open(page);

    // the embedded faces load from the deck folder (no system fallback for the headline)
    expect(await page.evaluate(() => document.fonts.check('500 52px "Funnel Display"') && document.fonts.check('400 16px "Funnel Sans"'))).toBe(true);
    expect(await page.evaluate(async () => (await Promise.all([...document.fonts].map((f) => f.load()))).filter((f) => f.status === 'loaded').length)).toBe(4);

    // every tagged number equals the value tools/deck-data.mjs computed from results/
    const mism = await page.evaluate(() => {
      const N = (window as any).DECK_DATA.N as Record<string, string>;
      return [...document.querySelectorAll<HTMLElement>('[data-n]')].filter((e) => N[e.dataset.n!] !== e.textContent!.trim()).map((e) => `${e.dataset.n}: "${e.textContent}" ≠ "${N[e.dataset.n!]}"`);
    });
    expect(mism).toEqual([]);

    const labels = await page.locator('.slide').evaluateAll((s) => s.map((x) => (x as HTMLElement).dataset.label!));
    expect(labels).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', 'A1', 'A2', 'A3', 'A4', 'A5']);

    // the stage is 16:9 and fills the window's limiting side
    const st = await page.locator('#stage').boundingBox();
    expect(Math.abs(st!.width / st!.height - 16 / 9)).toBeLessThan(0.01);
    expect(Math.min(Math.abs(st!.width - vp.width), Math.abs(st!.height - vp.height))).toBeLessThan(1.5);
    expect(st!.x).toBeGreaterThanOrEqual(-0.5);
    expect(st!.y).toBeGreaterThanOrEqual(-0.5);
    expect(st!.x + st!.width).toBeLessThanOrEqual(vp.width + 0.5);
    expect(st!.y + st!.height).toBeLessThanOrEqual(vp.height + 0.5);

    await page.keyboard.press('Home');
    for (let i = 0; i < labels.length; i++) {
      const lab = labels[i];
      if (i > 0) await page.keyboard.press(i % 2 ? 'ArrowRight' : ' ');
      const on = page.locator('.slide.on');
      await expect(on).toHaveCount(1);
      await expect(on).toHaveAttribute('data-label', lab);
      await expect(page.locator('#counter')).toHaveText(lab.startsWith('A') ? `${lab} · appendix` : `${lab} / 8`);
      // nothing spills outside the stage
      const spill = await on.evaluate((s) => {
        const r = document.getElementById('stage')!.getBoundingClientRect();
        return [...s.querySelectorAll('*')].filter((e) => {
          const b = e.getBoundingClientRect();
          if ((!b.width && !b.height) || e.closest('.crop') !== e && e.closest('.crop')) return false;
          return b.left < r.left - 1 || b.top < r.top - 1 || b.right > r.right + 1 || b.bottom > r.bottom + 1;
        }).map((e) => `${e.tagName}.${(e as HTMLElement).className}: ${(e.textContent ?? '').slice(0, 40)}`);
      });
      expect(spill, `slide ${lab}`).toEqual([]);
      // beat slides carry their dashboard deep link
      const link = on.locator('a.dash');
      if (LINKS[lab]) await expect(link).toHaveAttribute('href', `http://127.0.0.1:4173/${LINKS[lab]}`);
      else await expect(link).toHaveCount(0);
      // presenter notes: N shows this slide's lines, N hides them
      await page.keyboard.press('n');
      await expect(page.locator('#notes')).toBeVisible();
      if (process.env.DECK_SHOTS && lab === '5') await page.screenshot({ path: `${shots}/deck-05-notes-${vp.width}.png` });
      if (lab.length === 1 && Number(lab) > 1) await expect(page.locator('#notes')).toContainText(/Beat \d/);
      await page.keyboard.press('n');
      await expect(page.locator('#notes')).toBeHidden();
      if (process.env.DECK_SHOTS) await page.screenshot({ path: `${shots}/deck-${lab.padStart(2, '0')}-${vp.width}.png` });
    }

    // End, Home, number keys and the appendix key
    await page.keyboard.press('End');
    await expect(page.locator('.slide.on')).toHaveAttribute('data-label', '8');
    await page.keyboard.press('Home');
    await expect(page.locator('.slide.on')).toHaveAttribute('data-label', '1');
    await page.keyboard.press('5');
    await expect(page.locator('.slide.on')).toHaveAttribute('data-label', '5');
    await page.keyboard.press('ArrowLeft');
    await expect(page.locator('.slide.on')).toHaveAttribute('data-label', '4');
    await page.keyboard.press('9');
    await expect(page.locator('.slide.on')).toHaveAttribute('data-label', 'A1');
    // a reload keeps the slide
    await page.reload();
    await expect(page.locator('.slide.on')).toHaveAttribute('data-label', 'A1');

    expect(net, 'no network request').toEqual([]);
    expect(errors, 'no console error or warning').toEqual([]);
  });
}
