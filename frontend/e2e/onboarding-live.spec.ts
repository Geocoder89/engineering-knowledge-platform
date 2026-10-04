import { createHash, randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test, expect } from "@playwright/test";

async function capturedLink(email: string) {
  const directory =
    process.env.BROWSER_AUTH_OUTBOX_DIR ||
    join(tmpdir(), "decision-browser-outbox");
  const key = createHash("sha256").update(email).digest("hex");
  return JSON.parse(await readFile(join(directory, `${key}.json`), "utf8"))
    .verification_url as string;
}

test("real registration, resend, one-time verification, login and logout", async ({
  page,
}) => {
  test.skip(
    process.env.RUN_BROWSER_AUTH_TESTS !== "1",
    "Requires the disposable PostgreSQL-backed API fixture.",
  );
  const email = `onboarding-${randomUUID()}@example.test`;
  const password = "Local-onboarding-fixture-2026";
  await page.goto("/register");
  await page.getByLabel("Display name").fill("Onboarding Reviewer");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Check your inbox." }),
  ).toBeVisible();
  const originalLink = await capturedLink(email);

  await page.getByRole("link", { name: "Go to sign in" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "make sure your email is verified",
  );

  await page.getByRole("link", { name: "Resend verification email" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Send verification link" }).click();
  await expect(page.getByRole("status")).toContainText("If this email belongs");
  const latestLink = await capturedLink(email);
  expect(latestLink).not.toBe(originalLink);

  await page.goto(originalLink);
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "invalid, expired, or already used",
  );
  await page.goto(latestLink);
  await expect(page).toHaveURL(/\/verify-email$/);
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Email verified." }),
  ).toBeVisible();
  // Reusing the consumed token must be rejected by the real backend.
  await page.goto(latestLink);
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "invalid, expired, or already used",
  );
  await page.getByRole("link", { name: "Go to sign in" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
});
