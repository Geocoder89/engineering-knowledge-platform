import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const account = {
  id: "demo-id",
  email: "samuel@example.com",
  display_name: "Samuel",
  status: "active",
};
async function accessible(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
}
async function fillRegistration(page: Page) {
  await page.getByLabel("Display name").fill("Samuel");
  await page.getByLabel("Email address").fill(account.email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("a local test passphrase");
}

test("registers once, clears the password form, and offers the next steps", async ({
  page,
}) => {
  let requests = 0;
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/auth/register", async (route) => {
    requests++;
    expect(route.request().postDataJSON()).toEqual({
      email: account.email,
      display_name: "Samuel",
      password: "a local test passphrase",
    });
    await pending;
    await route.fulfill({ status: 201, json: account });
  });
  await page.goto("/register");
  await accessible(page);
  await fillRegistration(page);
  await page.getByRole("button", { name: "Show password" }).click();
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute(
    "type",
    "text",
  );
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Creating account…" }),
  ).toBeDisabled();
  release();
  await expect(
    page.getByRole("heading", { name: "Check your inbox." }),
  ).toBeVisible();
  expect(requests).toBe(1);
  await expect(page.getByLabel("Password", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("status")).toContainText(account.email);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
  await accessible(page);
  await page.getByRole("button", { name: "Use a different email" }).click();
  await expect(page.getByLabel("Email address")).toHaveValue("");
});

test("validates name, email and password before creating an account", async ({
  page,
}) => {
  let requests = 0;
  await page.route("**/api/**", (route) => {
    requests++;
    return route.abort();
  });
  await page.goto("/register");
  await fillRegistration(page);
  await page.getByLabel("Password", { exact: true }).fill("short");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  expect(
    await page
      .getByLabel("Password", { exact: true })
      .evaluate((input: HTMLInputElement) => input.validity.tooShort),
  ).toBe(true);
  await fillRegistration(page);
  await page.getByLabel("Email address").fill("invalid-email");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  expect(
    await page
      .getByLabel("Email address")
      .evaluate((input: HTMLInputElement) => input.validity.typeMismatch),
  ).toBe(true);
  await fillRegistration(page);
  await page.getByLabel("Display name").fill("   ");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("not blank");
  expect(requests).toBe(0);
});

for (const scenario of [
  { status: 409, message: "Try signing in" },
  { status: 422, message: "check the information" },
  { status: 429, message: "Too many attempts" },
  { status: 503, message: "could not send your verification email" },
  { status: 0, message: "could not reach the service" },
]) {
  test(`registration recovers from ${scenario.status || "network failure"}`, async ({
    page,
  }) => {
    let fail = true;
    await page.route("**/api/auth/register", (route) => {
      if (!fail) return route.fulfill({ status: 201, json: account });
      if (!scenario.status) return route.abort();
      return route.fulfill({
        status: scenario.status,
        json: { detail: "SECRET_INTERNAL_INPUT" },
        headers: {
          "X-Request-ID": "registration-reference",
          "Retry-After": "120",
        },
      });
    });
    await page.goto("/register");
    await fillRegistration(page);
    await page
      .getByRole("button", { name: "Create account", exact: true })
      .click();
    await expect(page.getByRole("alert")).toContainText(scenario.message);
    await expect(page.getByRole("alert")).not.toContainText(
      "SECRET_INTERNAL_INPUT",
    );
    await expect(page.getByLabel("Email address")).toHaveValue(account.email);
    if (scenario.status)
      await expect(page.getByRole("alert")).toContainText(
        "registration-reference",
      );
    if (scenario.status === 429)
      await expect(page.getByRole("alert")).toContainText("2 minutes");
    await accessible(page);
    fail = false;
    await page
      .getByRole("button", { name: "Create account", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Check your inbox." }),
    ).toBeVisible();
  });
}

test("removes the link token, waits for confirmation, and verifies only once", async ({
  page,
}) => {
  let requests = 0;
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/auth/verify-email", async (route) => {
    requests++;
    expect(route.request().postDataJSON()).toEqual({
      verification_token: "private-fixture-token",
    });
    expect(route.request().headers()["referer"]).toBeUndefined();
    await pending;
    await route.fulfill({ status: 204 });
  });
  await page.goto("/verify-email?token=private-fixture-token");
  await expect(page).toHaveURL(/\/verify-email$/);
  await expect(
    page.getByRole("button", { name: "Verify email", exact: true }),
  ).toBeVisible();
  expect(requests).toBe(0);
  expect(
    await page.evaluate(() =>
      JSON.stringify([
        history.state,
        { ...localStorage },
        { ...sessionStorage },
      ]),
    ),
  ).not.toContain("private-fixture-token");
  await accessible(page);
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Verifying email…" }),
  ).toBeDisabled();
  release();
  await expect(
    page.getByRole("heading", { name: "Email verified." }),
  ).toBeVisible();
  expect(requests).toBe(1);
  await accessible(page);
});

for (const query of [
  "",
  "?token=",
  "?token=one&token=two",
  `?token=${"x".repeat(257)}`,
]) {
  test(`missing or malformed verification link (${query.length})`, async ({
    page,
  }) => {
    let requests = 0;
    await page.route("**/api/**", (route) => {
      requests++;
      return route.abort();
    });
    await page.goto(`/verify-email${query}`);
    await expect(page.getByRole("status")).toContainText(
      "needs a verification link",
    );
    await expect(
      page.getByRole("button", { name: "Verify email", exact: true }),
    ).toHaveCount(0);
    await expect(page).toHaveURL(/\/verify-email$/);
    expect(requests).toBe(0);
  });
}

test("an invalid, expired or consumed token offers sign-in and resend", async ({
  page,
}) => {
  await page.route("**/api/auth/verify-email", (route) =>
    route.fulfill({ status: 400, json: { detail: "raw private token" } }),
  );
  await page.goto("/verify-email?token=expired-fixture");
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "invalid, expired, or already used",
  );
  await expect(page.getByRole("alert")).not.toContainText("raw private token");
  await expect(
    page.getByRole("button", { name: "Verify email", exact: true }),
  ).toHaveCount(0);
  await accessible(page);
  await page
    .getByRole("link", { name: "Request a new verification link" })
    .click();
  await expect(page).toHaveURL(/\/resend-verification$/);
});

test("verification can retry after an outage, but refresh requires reopening the email", async ({
  page,
}) => {
  let fail = true;
  await page.route("**/api/auth/verify-email", (route) =>
    route.fulfill(fail ? { status: 503, json: {} } : { status: 204 }),
  );
  await page.goto("/verify-email?token=retry-fixture");
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Email verified." }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByRole("status")).toContainText("reopen the email link");
});

test("resend accepts an empty 202 and never claims an account exists", async ({
  page,
}) => {
  await page.route("**/api/auth/resend-verification", (route) => {
    expect(route.request().postDataJSON()).toEqual({ email: account.email });
    return route.fulfill({ status: 202, body: "" });
  });
  await page.goto("/resend-verification");
  await accessible(page);
  await page.getByLabel("Email address").fill(account.email);
  await page.getByRole("button", { name: "Send verification link" }).click();
  await expect(page.getByRole("status")).toContainText(
    "If this email belongs to an account awaiting verification",
  );
  await expect(page.getByRole("alert")).toHaveCount(0);
  await accessible(page);
});

test("resend preserves email on rate limiting and supports retry", async ({
  page,
}) => {
  let fail = true;
  await page.route("**/api/auth/resend-verification", (route) =>
    route.fulfill(
      fail
        ? { status: 429, json: {}, headers: { "Retry-After": "120" } }
        : { status: 202, body: "" },
    ),
  );
  await page.goto("/resend-verification");
  await page.getByLabel("Email address").fill(account.email);
  await page.getByRole("button", { name: "Send verification link" }).click();
  await expect(page.getByRole("alert")).toContainText("2 minutes");
  await expect(page.getByLabel("Email address")).toHaveValue(account.email);
  fail = false;
  await page.getByRole("button", { name: "Send verification link" }).click();
  await expect(page.getByRole("status")).toBeVisible();
});
