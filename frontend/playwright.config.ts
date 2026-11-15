import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:4173/SpaceApps-AlairaX/",
    trace: "off",
  },
  webServer: {
    command: "npm run preview",
    url: "http://127.0.0.1:4173/SpaceApps-AlairaX/",
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
