import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:3001",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 5"] } },
  ],
  webServer: [
    {
      command:
        "cd ../../services/api && ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010",
      url: "http://127.0.0.1:8010/health",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command:
        "NEXT_PUBLIC_API_URL=http://127.0.0.1:8010 npm run dev -- --hostname 127.0.0.1 --port 3001",
      url: "http://127.0.0.1:3001",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
