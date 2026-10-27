import { defineConfig } from '@playwright/test';

// The installed browser is Playwright's chromium build 1243 (matches @playwright/test 1.63.0).
// PW_CHROMIUM overrides the path; on a machine with Playwright's own browsers, leave it unset.
const chromium = process.env.PW_CHROMIUM ?? '/home/nvidia/.cache/ms-playwright/chromium-1243/chrome-linux-arm64/chrome';
import { existsSync } from 'node:fs';

export default defineConfig({
  testDir: './tests',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:4173/',
    viewport: { width: 1728, height: 1117 },
    deviceScaleFactor: 1,
    launchOptions: {
      ...(existsSync(chromium) ? { executablePath: chromium } : {}),
      args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
    },
  },
  // Serves the built dist/ (run `npm run build` first) exactly as the Mac does.
  webServer: { command: 'npm run preview', url: 'http://127.0.0.1:4173/', reuseExistingServer: false, timeout: 60_000 },
});
