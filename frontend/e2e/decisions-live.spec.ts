import { randomUUID } from "node:crypto";
import { test, expect, type Page } from "@playwright/test";

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Browser-only-fixture-password-2026");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/workspace$/);
}

test("real decisions persist after reload and remain inaccessible to another account", async ({
  page,
  browser,
}, testInfo) => {
  test.skip(
    process.env.RUN_BROWSER_AUTH_TESTS !== "1",
    "Requires the disposable PostgreSQL-backed API fixture.",
  );
  const title = `Browser decision ${randomUUID()}`;
  const question = "Should we reduce the cooling-system pressure limit?";
  await login(page, `decisions-owner-${testInfo.project.name}@example.test`);
  await page.getByRole("link", { name: "Open your decisions" }).click();
  await page.getByRole("link", { name: "New decision", exact: true }).click();
  await page.getByLabel("Decision title").fill(title);
  await page.getByLabel("Question to resolve").fill(question);
  await page
    .getByRole("button", { name: "Save decision", exact: true })
    .click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
  const recordUrl = page.url();
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
  await expect(page.getByText(question, { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "All decisions" }).click();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();

  // A separate browser context has a separate session and cookie jar.
  const otherContext = await browser.newContext({
    baseURL: "http://127.0.0.1:5173",
  });
  try {
    const other = await otherContext.newPage();
    await login(other, `decisions-other-${testInfo.project.name}@example.test`);
    await other.getByRole("link", { name: "Open your decisions" }).click();
    await expect(
      other.getByRole("heading", {
        name: "Every decision starts with a question.",
      }),
    ).toBeVisible();
    await expect(other.getByText(title, { exact: true })).toHaveCount(0);
    const forbiddenResponse = other.waitForResponse((response) =>
      response.url().endsWith("/record"),
    );
    await other.goto(recordUrl);
    expect((await forbiddenResponse).status()).toBe(404);
    await expect(
      other.getByRole("heading", { name: "Decision unavailable." }),
    ).toBeVisible();
    await expect(other.getByText(question, { exact: true })).toHaveCount(0);
  } finally {
    await otherContext.close();
  }

  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.goto(recordUrl);
  await expect(page).toHaveURL(/\/login$/);
});
