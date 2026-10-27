import { defineConfig } from '@playwright/test';

// The installed browser is Playwright's chromium build 1243 (matches @playwright/test 1.63.0).
// PW_CHROMIUM overrides the path; on a machine with Playwright's own browsers, leave it unset.
const chromium = process.env.PW_CHROMIUM ?? '/home/nvidia/.cache/ms-playwright/chromium-1243/chrome-linux-arm64/chrome';
import { existsSync } from 'node:fs';
// PW_PORT runs the preview on another port, so parallel worktrees never share (or collide on) 4173.
const port = Number(process.env.PW_PORT ?? 4173);

export default defineConfig({
  testDir: './tests',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${port}/`,
    viewport: { width: 1728, height: 1117 },
    deviceScaleFactor: 1,
    launchOptions: {
      ...(existsSync(chromium) ? { executablePath: chromium } : {}),
      args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
    },
  },
  // Serves the built dist/ (run `npm run build` first) exactly as the Mac does.
  webServer: { command: port === 4173 ? 'npm run preview' : `npx vite preview --port ${port} --strictPort`, url: `http://127.0.0.1:${port}/`, reuseExistingServer: false, timeout: 60_000 },
});
