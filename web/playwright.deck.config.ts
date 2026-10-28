import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';

// The pitch deck (docs/pitch/deck) is a static page opened from file://, so no web server is needed
// and PW_PORT does not apply. Same browser as playwright.config.ts.
const chromium = process.env.PW_CHROMIUM ?? '/home/nvidia/.cache/ms-playwright/chromium-1243/chrome-linux-arm64/chrome';

export default defineConfig({
  testDir: './tests',
  testMatch: /deck\.spec\.ts/,
  timeout: 120_000,
  workers: 1,
  reporter: [['list']],
  use: {
    viewport: { width: 1728, height: 1117 },
    deviceScaleFactor: 1,
    reducedMotion: 'reduce',
    launchOptions: { ...(existsSync(chromium) ? { executablePath: chromium } : {}) },
  },
});
