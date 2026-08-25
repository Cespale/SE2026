import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 1,

  reporter: [
    ['list'],
    ['junit', { outputFile: 'reports/e2e-tests.xml' }],
  ],

  use: {
    baseURL: 'http://127.0.0.1:3266',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },

  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:3266',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});