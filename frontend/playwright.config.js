import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: '../browser_artifacts/playwright-report', open: 'never' }]],
  outputDir: '../browser_artifacts/test-results',
  use: {
    baseURL: 'http://127.0.0.1:15174',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: '../venv/bin/python ../scripts/run_browser_test_backend.py',
      url: 'http://127.0.0.1:18001/health',
      cwd: '.',
      timeout: 60_000,
      reuseExistingServer: false,
    },
    {
      command: 'VITE_API_BASE_URL=http://127.0.0.1:18001 npm run dev -- --host 127.0.0.1 --port 15174',
      url: 'http://127.0.0.1:15174',
      cwd: '.',
      timeout: 60_000,
      reuseExistingServer: false,
    },
  ],
  projects: [
    { name: 'desktop-1440', use: { browserName: 'chromium', viewport: { width: 1440, height: 900 } } },
    { name: 'desktop-1280', use: { browserName: 'chromium', viewport: { width: 1280, height: 800 } } },
    { name: 'tablet', use: { browserName: 'chromium', viewport: { width: 768, height: 1024 } } },
    { name: 'mobile', use: { browserName: 'chromium', viewport: { width: 390, height: 844 } } },
  ],
})
