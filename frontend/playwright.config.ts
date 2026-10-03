import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : undefined,
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    ...(process.env.RUN_BROWSER_AUTH_TESTS === "1"
      ? [
          {
            command: "cd .. && python -m scripts.browser_auth_server",
            url: "http://127.0.0.1:8001/health",
            reuseExistingServer: false,
            timeout: 60000,
          },
        ]
      : []),
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer:
        !process.env.CI && process.env.RUN_BROWSER_AUTH_TESTS !== "1",
    },
  ],
});
