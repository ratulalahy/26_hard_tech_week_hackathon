// Serve the synthetic results/test fixture (T11 B6) to the built dashboard through Playwright routes, so the
// test-year state can be checked without ever putting the fixture under public/ or dist/.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { Page } from '@playwright/test';
import { FIXTURE_DIR, fixtureManifest } from './expected';

export async function serveTestFixture(page: Page) {
  await page.context().route('**/data/results/index.json', async (route) => {
    const r = await route.fetch();
    const idx = await r.json();
    idx.test = { available: true, files: ['forecast-replay.json', 'grid-profile.json', 'job-replay.json', 'manifest.json', 'metrics.json', 'workload-profile.json'], frozen_at: fixtureManifest.freeze.wallclock_frozen_at };
    await route.fulfill({ response: r, json: idx });
  });
  await page.context().route('**/data/results/test/*.json', (route) => {
    const name = new URL(route.request().url()).pathname.split('/').pop()!;
    return route.fulfill({ status: 200, contentType: 'application/json', body: readFileSync(join(FIXTURE_DIR, name), 'utf8') });
  });
}

/** Pick the test year in the top bar's window switch and wait for its results. */
export async function openTestYear(page: Page) {
  await page.getByRole('radio', { name: /^Test year/ }).click();
  await page.getByRole('radio', { name: /^Test year/ }).and(page.locator('[aria-checked="true"]')).waitFor();
}
