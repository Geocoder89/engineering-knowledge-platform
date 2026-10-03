import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const user = {
  id: "bfe2a1af-ff66-4ef2-b5e9-397519328b87",
  email: "engineer@example.com",
  display_name: "Sam Engineer",
  status: "active",
};

async function mockSession(page: Page, initial = false) {
  const state = {
    authenticated: initial,
    meStatus: 0,
    loginStatus: 200,
    logoutStatus: 204,
    logins: 0,
    logoutToken: "",
  };
  await page.context().addCookies([
    {
      name: "decision_csrf",
      value: "csrf-test-value",
      url: "http://127.0.0.1:5173",
    },
  ]);
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/users/me") {
      const status = state.meStatus || (state.authenticated ? 200 : 401);
      await route.fulfill({
        status,
        json:
          status === 200 ? user : { detail: "Do not display raw server data" },
        headers: { "X-Request-ID": "session-request" },
      });
    } else if (path === "/api/auth/login") {
      state.logins++;
      expect(route.request().postDataJSON()).toEqual({
        email: user.email,
        password: "correct horse battery staple",
      });
      if (state.loginStatus === 200) state.authenticated = true;
      await route.fulfill({
        status: state.loginStatus,
        json:
          state.loginStatus === 200
            ? user
            : { detail: "Private server message" },
        headers: { "Retry-After": "120", "X-Request-ID": "login-request" },
      });
    } else if (path === "/api/auth/logout") {
      state.logoutToken = route.request().headers()["x-csrf-token"] ?? "";
      if (state.logoutStatus === 204) state.authenticated = false;
      await route.fulfill({
        status: state.logoutStatus,
        body:
          state.logoutStatus === 204
            ? ""
            : JSON.stringify({ detail: "Private logout detail" }),
      });
    } else {
      throw new Error(`Unexpected API request: ${path}`);
    }
  });
  return state;
}
async function signIn(page: Page) {
  await page.getByLabel("Email address").fill(user.email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("correct horse battery staple");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}
async function accessible(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    result.violations.map(({ id, nodes }) => ({
      id,
      targets: nodes.map((node) => node.target),
    })),
  ).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
}

test("protects the workspace, signs in, restores the session, and revokes it on logout", async ({
  page,
}) => {
  const state = await mockSession(page);
  await page.goto("/workspace");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText(user.email, { exact: true })).not.toBeVisible();
  await accessible(page);
  await page.getByRole("button", { name: "Show password" }).click();
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute(
    "type",
    "text",
  );
  await page.getByRole("button", { name: "Hide password" }).click();
  await signIn(page);
  await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    user.display_name,
  );
  await accessible(page);
  await page.reload();
  await expect(page.getByText(user.email, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(state.logoutToken).toBe("csrf-test-value");
  await expect(page.getByText("You have been signed out.")).toBeVisible();
  expect(
    await page.evaluate(() => ({
      local: localStorage.length,
      session: sessionStorage.length,
    })),
  ).toEqual({ local: 0, session: 0 });
  await page.goBack();
  await page.goto("/workspace");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText(user.email, { exact: true })).not.toBeVisible();
});

test("shows safe credential and rate-limit errors without signing the user in", async ({
  page,
}) => {
  const state = await mockSession(page);
  state.loginStatus = 401;
  await page.goto("/login");
  await signIn(page);
  await expect(page.getByRole("alert")).toContainText(
    "Check your email and password",
  );
  await expect(page.getByRole("alert")).not.toContainText(
    "Private server message",
  );
  state.loginStatus = 429;
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("2 minutes");
  await expect(page.getByRole("alert")).toContainText("login-request");
  await expect(page).toHaveURL(/\/login$/);
  expect(state.logins).toBe(2);
});

test("distinguishes an unavailable API from an anonymous session and retries", async ({
  page,
}) => {
  const state = await mockSession(page, true);
  state.meStatus = 503;
  await page.goto("/workspace");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Let’s reconnect.",
  );
  await expect(page.getByText(user.email, { exact: true })).not.toBeVisible();
  await accessible(page);
  state.meStatus = 0;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByText(user.email, { exact: true })).toBeVisible();
});

test("redirects an expired session when the window regains focus", async ({
  page,
}) => {
  const state = await mockSession(page, true);
  await page.goto("/workspace");
  await expect(page.getByText(user.email, { exact: true })).toBeVisible();
  state.authenticated = false;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("status")).toContainText(
    "Your session has ended",
  );
  await expect(page.getByText(user.email, { exact: true })).not.toBeVisible();
});

test("keeps the session on a failed logout and allows retry", async ({
  page,
}) => {
  const state = await mockSession(page, true);
  state.logoutStatus = 403;
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("could not be verified");
  await expect(page.getByText(user.email, { exact: true })).toBeVisible();
  state.logoutStatus = 204;
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("sample routes work without an API or an account", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) requests.push(request.url());
  });
  await page.goto("/preview");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Every decision",
  );
  expect(requests).toEqual([]);
});

test("handles a network error and an unexpected successful response", async ({
  page,
}) => {
  await page.route("**/api/users/me", (route) => route.abort("failed"));
  await page.goto("/workspace");
  await expect(page.getByRole("alert")).toContainText("could not reach");
  await page.route("**/api/users/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<h1>Unexpected upstream page</h1>",
    }),
  );
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("alert")).toContainText("unexpected response");
  await expect(page.getByRole("alert")).not.toContainText(
    "Unexpected upstream page",
  );
});

test("a cookie that is not accepted cannot open the workspace", async ({
  page,
}) => {
  const state = await mockSession(page);
  state.meStatus = 401;
  await page.goto("/login");
  await signIn(page);
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test("logout in another tab prompts a fresh session check", async ({
  page,
  context,
}) => {
  await mockSession(page, true);
  await page.goto("/workspace");
  await expect(page.getByText(user.email, { exact: true })).toBeVisible();
  const other = await context.newPage();
  const otherState = await mockSession(other, true);
  await other.goto("/workspace");
  await expect(other.getByText(user.email, { exact: true })).toBeVisible();
  otherState.authenticated = false;
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(other).toHaveURL(/\/login$/);
  await expect(other.getByRole("status")).toContainText(
    "Your session has ended",
  );
});

test("a delayed session check cannot restore an account after logout", async ({
  page,
}) => {
  await mockSession(page, true);
  await page.goto("/workspace");
  await expect(page.getByText(user.email, { exact: true })).toBeVisible();
  let release!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  let requested = false;
  await page.route("**/api/users/me", async (route) => {
    requested = true;
    await held;
    await route.fulfill({ status: 200, json: user }).catch(() => {});
  });
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect.poll(() => requested).toBe(true);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  release();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("status")).toContainText(
    "You have been signed out",
  );
  await expect(page.getByText(user.email, { exact: true })).not.toBeVisible();
});
