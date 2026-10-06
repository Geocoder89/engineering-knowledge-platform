import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { user, decision, record } from "./decision-fixtures";

async function session(page: Page) {
  await page.route("**/api/users/me", (route) => route.fulfill({ json: user }));
  await page.context().addCookies([
    {
      name: "decision_csrf",
      value: "decision-test-token",
      url: "http://127.0.0.1:5173",
    },
  ]);
}
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
async function fill(page: Page) {
  await page.getByLabel("Decision title").fill(decision.title);
  await page.getByLabel("Question to resolve").fill(decision.question);
}

test("empty register, validation, one create request, saved record and refresh", async ({
  page,
}) => {
  await session(page);
  let created = false,
    posts = 0;
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/decisions?*", (route) =>
    route.fulfill({
      json: {
        items: created ? [decision] : [],
        total: created ? 1 : 0,
        offset: 0,
        limit: 20,
      },
    }),
  );
  await page.route("**/api/decisions", async (route) => {
    posts++;
    expect(route.request().postDataJSON()).toEqual({
      title: decision.title,
      question: decision.question,
    });
    expect(route.request().headers()["x-csrf-token"]).toBe(
      "decision-test-token",
    );
    await pending;
    created = true;
    await route.fulfill({ status: 201, json: decision });
  });
  await page.route("**/api/decisions/*/record", (route) =>
    route.fulfill({ json: record }),
  );
  await page.goto("/workspace/decisions");
  await expect(
    page.getByRole("heading", {
      name: "Every decision starts with a question.",
    }),
  ).toBeVisible();
  await accessible(page);
  await page.getByRole("link", { name: "Create your first decision" }).click();
  await accessible(page);
  await fill(page);
  await page.getByLabel("Decision title").fill("    ");
  await page
    .getByRole("button", { name: "Save decision", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "excluding surrounding spaces",
  );
  expect(posts).toBe(0);
  await fill(page);
  await page
    .getByRole("button", { name: "Save decision", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Saving decision…" }),
  ).toBeDisabled();
  release();
  await expect(page).toHaveURL(`/workspace/decisions/${decision.id}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    decision.title,
  );
  await expect(
    page.getByText(decision.question, { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("No alternatives have been added to this decision yet."),
  ).toBeVisible();
  expect(posts).toBe(1);
  await accessible(page);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    decision.title,
  );
  await page.getByRole("link", { name: "All decisions" }).click();
  await expect(
    page.getByRole("heading", { name: decision.title }),
  ).toBeVisible();
});

test("pagination is URL-backed and changing pages hides the previous records", async ({
  page,
}) => {
  await session(page);
  const second = {
    ...decision,
    id: "72cd9e2e-c626-450e-9f00-7b3c89b3ecb2",
    title: "Second page decision",
  };
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/decisions?*", async (route) => {
    const offset = Number(
      new URL(route.request().url()).searchParams.get("offset"),
    );
    if (offset === 20) await pending;
    await route.fulfill({
      json: {
        items: [offset ? second : decision],
        total: 21,
        offset,
        limit: 20,
      },
    });
  });
  await page.goto("/workspace/decisions");
  await expect(
    page.getByRole("heading", { name: decision.title }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Loading");
  await expect(page.getByRole("heading", { name: decision.title })).toHaveCount(
    0,
  );
  release();
  await expect(page).toHaveURL(/offset=20$/);
  await expect(page.getByRole("heading", { name: second.title })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Next", exact: true }),
  ).toBeDisabled();
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: decision.title }),
  ).toBeVisible();
  await accessible(page);
});

test("list and record failures offer retries and reject malformed success data", async ({
  page,
}) => {
  await session(page);
  let fail = true;
  await page.route("**/api/decisions?*", (route) =>
    route.fulfill(
      fail
        ? {
            status: 503,
            json: { detail: "PRIVATE_DATABASE_ERROR" },
            headers: { "X-Request-ID": "decisions-reference" },
          }
        : { json: { items: [decision], total: 1, offset: 0, limit: 20 } },
    ),
  );
  await page.goto("/workspace/decisions");
  await expect(page.getByRole("alert")).toContainText("decisions-reference");
  await expect(page.getByRole("alert")).not.toContainText(
    "PRIVATE_DATABASE_ERROR",
  );
  fail = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { name: decision.title }),
  ).toBeVisible();
  let malformed = true;
  await page.route("**/api/decisions/*/record", (route) =>
    route.fulfill({ json: malformed ? {} : record }),
  );
  await page.getByRole("link", { name: new RegExp(decision.title) }).click();
  await expect(page.getByRole("alert")).toContainText(
    "incomplete decision record",
  );
  malformed = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    decision.title,
  );
});

test("existing outcome, evidence and unknown historical attribution are rendered", async ({
  page,
}) => {
  await session(page);
  const alternativeId = "67cd9e2e-c626-450e-9f00-7b3c89b3ecb2";
  await page.route("**/api/decisions/*/record", (route) =>
    route.fulfill({
      json: {
        ...record,
        created_by_user_id: null,
        status: "decided",
        rationale: "Reduce the limit based on the documented safety margin.",
        selected_alternative_id: alternativeId,
        decided_at: decision.created_at,
        alternatives: [
          {
            id: alternativeId,
            title: "Reduce pressure",
            description: "Lower the approved maximum pressure.",
            position: 0,
            evidence: [
              {
                id: "97cd9e2e-c626-450e-9f00-7b3c89b3ecb2",
                evidence_type: "supporting",
                text: "The recommended limit is lower than the current setting.",
                relevance_note: "Safety margin",
                citation: {
                  document_title: "Pressure report",
                  file_name: "pressure.pdf",
                  version_number: 2,
                  page_number: 3,
                },
              },
            ],
          },
        ],
      },
    }),
  );
  await page.goto(`/workspace/decisions/${decision.id}`);
  await expect(page.getByText("ALTERNATIVE 1 · SELECTED")).toBeVisible();
  await expect(
    page.getByText("Pressure report · pressure.pdf · Version 2, page 3"),
  ).toBeVisible();
  await expect(page.getByText("Not recorded", { exact: true })).toHaveCount(2);
  await accessible(page);
});

test("unknown, other-user and malformed record links have a safe unavailable state", async ({
  page,
}) => {
  await session(page);
  let reads = 0;
  await page.route("**/api/decisions/*/record", (route) => {
    reads++;
    return route.fulfill({
      status: 404,
      json: { detail: "PRIVATE_OTHER_USER_RECORD" },
    });
  });
  await page.goto("/workspace/decisions/not-a-uuid");
  await expect(
    page.getByRole("heading", { name: "Decision unavailable." }),
  ).toBeVisible();
  expect(reads).toBe(0);
  await page.goto(`/workspace/decisions/${decision.id}`);
  await expect(
    page.getByRole("heading", { name: "Decision unavailable." }),
  ).toBeVisible();
  await expect(page.getByText("PRIVATE_OTHER_USER_RECORD")).toHaveCount(0);
  await accessible(page);
});

for (const status of [422, 403, 0]) {
  test(`create keeps input and recovers after ${status || "network failure"}`, async ({
    page,
  }) => {
    await session(page);
    let fail = true;
    await page.route("**/api/decisions", (route) =>
      fail
        ? status
          ? route.fulfill({ status, json: { detail: "SECRET_INPUT" } })
          : route.abort()
        : route.fulfill({ status: 201, json: decision }),
    );
    await page.route("**/api/decisions/*/record", (route) =>
      route.fulfill({ json: record }),
    );
    await page.goto("/workspace/decisions/new");
    await fill(page);
    await page
      .getByRole("button", { name: "Save decision", exact: true })
      .click();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page.getByRole("alert")).not.toContainText("SECRET_INPUT");
    await expect(page.getByLabel("Decision title")).toHaveValue(decision.title);
    await expect(page.getByLabel("Question to resolve")).toHaveValue(
      decision.question,
    );
    if (!status)
      await expect(
        page.getByRole("link", { name: "Check your decisions" }),
      ).toBeVisible();
    fail = false;
    await page
      .getByRole("button", { name: "Save decision", exact: true })
      .click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      decision.title,
    );
  });
}

test("expired sessions return to the requested decision after login", async ({
  page,
}) => {
  let authenticated = true,
    expired = true;
  await page.route("**/api/users/me", (route) =>
    route.fulfill(authenticated ? { json: user } : { status: 401, json: {} }),
  );
  await page.route("**/api/decisions/*/record", (route) => {
    if (expired) {
      authenticated = false;
      return route.fulfill({ status: 401, json: {} });
    }
    return route.fulfill({ json: record });
  });
  await page.route("**/api/auth/login", (route) => {
    authenticated = true;
    expired = false;
    return route.fulfill({ json: user });
  });
  await page.goto(`/workspace/decisions/${decision.id}`);
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email address").fill(user.email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("a local password for testing");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(`/workspace/decisions/${decision.id}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    decision.title,
  );
});

test("switching the authenticated identity clears the prior account record", async ({
  page,
}) => {
  let changed = false;
  await page.route("**/api/users/me", (route) =>
    route.fulfill({
      json: changed
        ? { ...user, id: "afe2a1af-ff66-4ef2-b5e9-397519328b87" }
        : user,
    }),
  );
  await page.route("**/api/decisions/*/record", (route) =>
    route.fulfill(changed ? { status: 404, json: {} } : { json: record }),
  );
  await page.goto(`/workspace/decisions/${decision.id}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    decision.title,
  );
  changed = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(
    page.getByRole("heading", { name: "Decision unavailable." }),
  ).toBeVisible();
  await expect(page.getByText(decision.title, { exact: true })).toHaveCount(0);
});
