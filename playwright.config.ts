import { defineConfig } from '@playwright/test';

const useMicroservicesStack =
  process.env.E2E_USE_MICROSERVICES === 'true';
const frontendPort =
  process.env.E2E_FRONTEND_PORT || (useMicroservicesStack ? '5273' : '3267');
const backendPort = process.env.E2E_BACKEND_PORT || '8001';
const baseURL =
  process.env.E2E_BASE_URL ||
  (useMicroservicesStack
    ? 'http://127.0.0.1:5273'
    : `http://127.0.0.1:${frontendPort}`);
const backendURL =
  process.env.E2E_BACKEND_URL ||
  (useMicroservicesStack
    ? 'http://127.0.0.1:8100'
    : `http://127.0.0.1:${backendPort}`);
const artifactDir = process.env.E2E_ARTIFACT_DIR || 'test-results';
const junitOutput = process.env.E2E_JUNIT_OUTPUT || 'reports/e2e-tests.xml';

// 后端启动用的 Python 解释器：
// - CI(Linux)：用 python（setup-python 提供）
// - 本地 Windows：默认用 backend/.venv 里的解释器（前斜杠在 Windows 上同样有效）
// 也可用环境变量 E2E_BACKEND_PYTHON 覆盖。
const backendPython =
  process.env.E2E_BACKEND_PYTHON ||
  (process.platform === 'win32' ? '.venv/Scripts/python.exe' : 'python');

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

  ...(useMicroservicesStack ? {} : { webServer: [
    {
      command: `${backendPython} -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      cwd: './backend',
      env: {
        ...process.env,
        CORS_ORIGINS: baseURL,
        MINIO_ACCESS_KEY: process.env.MINIO_ACCESS_KEY || 'streamhub-e2e',
        MINIO_SECRET_KEY: process.env.MINIO_SECRET_KEY || 'streamhub-e2e-secret',
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
      env: {
        ...process.env,
        REACT_APP_API_BASE_URL: backendURL,
        STREAMHUB_BACKEND_PROXY_TARGET: backendURL,
      },
      url: baseURL,
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: 'ignore',
      stderr: 'pipe',
    },
  ] }),
});
