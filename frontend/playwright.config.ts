import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:3001", trace: "on-first-retry" },
  webServer: { command: "npm run dev -- --port 3001", url: "http://127.0.0.1:3001", reuseExistingServer: true },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
