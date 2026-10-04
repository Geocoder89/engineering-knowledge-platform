import { test, expect } from "@playwright/test";

test("real API login, cookie restoration, CSRF rejection, and session revocation", async ({
  page,
  context,
}, testInfo) => {
  test.skip(
    process.env.RUN_BROWSER_AUTH_TESTS !== "1",
    "Requires the disposable PostgreSQL-backed API fixture.",
  );
  await page.goto("/workspace");
  await expect(page).toHaveURL(/\/login$/);
  await page
    .getByLabel("Email address")
    .fill(`browser-${testInfo.project.name}@example.test`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Browser-only-fixture-password-2026");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    `Browser ${testInfo.project.name === "desktop" ? "Desktop" : "Mobile"}`,
  );
  const cookies = await context.cookies();
  const session = cookies.find((cookie) => cookie.name === "decision_session");
  const csrf = cookies.find((cookie) => cookie.name === "decision_csrf");
  expect(session?.httpOnly).toBe(true);
  expect(csrf?.httpOnly).toBe(false);
  expect(await page.evaluate(() => document.cookie)).not.toContain(
    "decision_session",
  );
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Your account", exact: true }),
  ).toBeVisible();
  // Requests without the double-submit token or from an untrusted origin must fail.
  const missingToken = await context.request.post("/api/auth/logout", {
    headers: { Origin: "http://127.0.0.1:5173" },
  });
  expect(missingToken.status()).toBe(403);
  const wrongOrigin = await context.request.post("/api/auth/logout", {
    headers: {
      Origin: "https://untrusted.example",
      "X-CSRF-Token": csrf!.value,
    },
  });
  expect(wrongOrigin.status()).toBe(403);
  const stillSignedIn = await context.request.get("/api/users/me");
  expect(stillSignedIn.status()).toBe(200);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect((await context.request.get("/api/users/me")).status()).toBe(401);
  // Replaying the old cookie must also fail: logout revoked the database session.
  const replay = await context.request.get("/api/users/me", {
    headers: { Cookie: `decision_session=${session!.value}` },
  });
  expect(replay.status()).toBe(401);
  expect(
    (await context.cookies()).some(
      (cookie) => cookie.name === "decision_session",
    ),
  ).toBe(false);

  // Both documented local addresses must work with real browser Origin headers.
  await page.goto("http://localhost:5173/login");
  await page
    .getByLabel("Email address")
    .fill(`browser-${testInfo.project.name}@example.test`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Browser-only-fixture-password-2026");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL("http://localhost:5173/workspace");
  await expect(
    page.getByRole("heading", { name: "Your account", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL("http://localhost:5173/login");
});
