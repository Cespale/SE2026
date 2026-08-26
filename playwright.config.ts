import { defineConfig } from '@playwright/test';

const frontendPort = process.env.E2E_FRONTEND_PORT || '3267';
const backendPort = process.env.E2E_BACKEND_PORT || '8001';
const baseURL = `http://127.0.0.1:${frontendPort}`;
const backendURL =
  process.env.E2E_BACKEND_URL || `http://127.0.0.1:${backendPort}`;
const artifactDir = process.env.E2E_ARTIFACT_DIR || 'test-results';
const junitOutput = process.env.E2E_JUNIT_OUTPUT || 'reports/e2e-tests.xml';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 1,

  reporter: [
    ['list'],
    ['junit', { outputFile: junitOutput }],
  ],

  outputDir: artifactDir,

  use: {
    baseURL,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },

  webServer: [
    {
      command: `.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      cwd: './backend',
      env: {
        ...process.env,
        CORS_ORIGINS: baseURL,
        PYTHONIOENCODING: 'utf-8',
      },
      url: `http://127.0.0.1:${backendPort}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: 'ignore',
      stderr: 'pipe',
    },
    {
      command: `npm run dev -- --port ${frontendPort}`,
      env: { ...process.env, REACT_APP_API_BASE_URL: backendURL },
      url: baseURL,
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: 'ignore',
      stderr: 'pipe',
    },
  ],
});
