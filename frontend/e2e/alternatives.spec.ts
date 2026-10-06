import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { user, decision, record } from "./decision-fixtures";

const initial = {
  id: "67cd9e2e-c626-450e-9f00-7b3c89b3ecb2",
  title: "Reduce pressure",
  description: "Lower the approved maximum pressure.",
  position: 0,
  evidence: [],
};
async function setup(page: Page, alternatives = [initial], status = "draft") {
  let current = { ...record, status, alternatives };
  await page.route("**/api/users/me", (route) => route.fulfill({ json: user }));
  await page.context().addCookies([
    {
      name: "decision_csrf",
      value: "alternatives-token",
      url: "http://127.0.0.1:5173",
    },
  ]);
  await page.route("**/api/decisions/*/record", (route) =>
    route.fulfill({ json: current }),
  );
  return {
    get: () => current,
    set: (next: typeof current) => {
      current = next;
    },
  };
}
async function open(page: Page) {
  await page.goto(`/workspace/decisions/${decision.id}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    decision.title,
  );
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

test("add validates, sends one CSRF-protected request, refreshes history and persists", async ({
  page,
}) => {
  const state = await setup(page, []);
  let posts = 0;
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/decisions/*/alternatives", async (route) => {
    posts++;
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers()["x-csrf-token"]).toBe(
      "alternatives-token",
    );
    expect(route.request().postDataJSON()).toEqual({
      title: initial.title,
      description: initial.description,
    });
    await pending;
    state.set({
      ...state.get(),
      alternatives: [initial],
      history: { ...record.history, total: 2 },
    });
    await route.fulfill({ status: 201, json: initial });
  });
  await open(page);
  await page
    .getByRole("button", { name: "Add alternative", exact: true })
    .click();
  await expect(page.getByLabel("Alternative title")).toBeFocused();
  await accessible(page);
  await expect(page.getByLabel("Alternative title")).toHaveAttribute(
    "maxlength",
    "200",
  );
  await expect(page.getByLabel("Description", { exact: true })).toHaveAttribute(
    "maxlength",
    "4000",
  );
  await page.getByLabel("Alternative title").fill("   ");
  await page
    .getByLabel("Description", { exact: true })
    .fill(initial.description);
  await page.getByRole("button", { name: "Save alternative" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "excluding surrounding spaces",
  );
  expect(posts).toBe(0);
  await page.getByLabel("Alternative title").fill(` ${initial.title} `);
  await page
    .getByLabel("Description", { exact: true })
    .fill(` ${initial.description} `);
  await page.getByRole("button", { name: "Save alternative" }).click();
  await expect(
    page.getByRole("button", { name: "Saving change…" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Cancel", exact: true }),
  ).toBeDisabled();
  release();
  await expect(page.getByRole("status")).toHaveText("Alternative added.");
  await expect(
    page.getByRole("heading", { name: "Alternatives", exact: true }),
  ).toBeFocused();
  await expect(
    page.getByRole("article", { name: initial.title }),
  ).toContainText("ALTERNATIVE 1");
  await expect(
    page
      .locator(".record-metadata dl > div")
      .filter({ hasText: "Audit events" })
      .locator("dd"),
  ).toHaveText("2");
  expect(posts).toBe(1);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: initial.title, exact: true }),
  ).toBeVisible();
  await accessible(page);
});

test("edit submits changed fields only; cancel restores focus and leaves saved values", async ({
  page,
}) => {
  const state = await setup(page);
  let patches = 0;
  await page.route("**/api/decisions/*/alternatives/*", async (route) => {
    patches++;
    expect(route.request().method()).toBe("PATCH");
    expect(route.request().headers()["x-csrf-token"]).toBe(
      "alternatives-token",
    );
    expect(route.request().postDataJSON()).toEqual({
      title: "Keep current pressure",
    });
    state.set({
      ...state.get(),
      alternatives: [{ ...initial, title: "Keep current pressure" }],
    });
    await route.fulfill({ json: {} });
  });
  await open(page);
  await page.getByRole("button", { name: "Edit alternative" }).click();
  await expect(page.getByLabel("Alternative title")).toHaveValue(initial.title);
  await expect(
    page.getByRole("button", { name: "Save changes" }),
  ).toBeDisabled();
  await page.getByLabel("Alternative title").fill("Unsaved option");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Edit alternative" }),
  ).toBeFocused();
  expect(patches).toBe(0);
  await page.getByRole("button", { name: "Edit alternative" }).click();
  await expect(page.getByLabel("Alternative title")).toHaveValue(initial.title);
  await page.getByLabel("Alternative title").fill("Keep current pressure");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status")).toHaveText("Alternative updated.");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Keep current pressure" }),
  ).toBeVisible();
  expect(patches).toBe(1);
});

test("removal requires confirmation, discloses linked evidence, and reloads server order", async ({
  page,
}) => {
  const second = {
    ...initial,
    id: "77cd9e2e-c626-450e-9f00-7b3c89b3ecb2",
    title: "Keep current pressure",
    position: 1,
  };
  const state = await setup(page, [initial, second]);
  // Record evidence is read-only in this slice; the removal warns about its loss.
  await page.route("**/api/decisions/*/record", (route) =>
    route.fulfill({
      json: {
        ...state.get(),
        alternatives: state.get().alternatives.map((item) =>
          item.id !== initial.id
            ? item
            : {
                ...item,
                evidence: [
                  {
                    id: "97cd9e2e-c626-450e-9f00-7b3c89b3ecb2",
                    evidence_type: "supporting",
                    text: "The lower limit improves the safety margin.",
                    relevance_note: null,
                    citation: {
                      document_title: "Pressure report",
                      file_name: "pressure.pdf",
                      version_number: 1,
                      page_number: 1,
                    },
                  },
                ],
              },
        ),
      },
    }),
  );
  let deletes = 0;
  await page.route("**/api/decisions/*/alternatives/*", async (route) => {
    deletes++;
    expect(route.request().method()).toBe("DELETE");
    expect(route.request().headers()["x-csrf-token"]).toBe(
      "alternatives-token",
    );
    state.set({ ...state.get(), alternatives: [{ ...second, position: 0 }] });
    await route.fulfill({ status: 204 });
  });
  await open(page);
  await page
    .getByRole("article", { name: initial.title })
    .getByRole("button", { name: "Remove alternative" })
    .click();
  await expect(
    page.getByRole("button", { name: "Cancel", exact: true }),
  ).toBeFocused();
  await expect(page.getByRole("form")).toContainText("1 linked evidence items");
  await expect(page.getByRole("form")).toContainText(
    "source documents remain available",
  );
  await accessible(page);
  expect(deletes).toBe(0);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  expect(deletes).toBe(0);
  await page
    .getByRole("article", { name: initial.title })
    .getByRole("button", { name: "Remove alternative" })
    .click();
  await page.getByRole("button", { name: "Confirm removal" }).click();
  await expect(page.getByRole("status")).toHaveText("Alternative removed.");
  await expect(page.getByRole("article", { name: initial.title })).toHaveCount(
    0,
  );
  await expect(page.getByRole("article", { name: second.title })).toContainText(
    "ALTERNATIVE 1",
  );
  expect(deletes).toBe(1);
});

for (const status of [422, 403, 429]) {
  test(`rejected save ${status} retains input, hides backend details and allows correction`, async ({
    page,
  }) => {
    const state = await setup(page);
    let fail = true;
    await page.route("**/api/decisions/*/alternatives/*", async (route) => {
      if (fail)
        return route.fulfill({
          status,
          json: { detail: "SECRET_INPUT" },
          headers: {
            "X-Request-ID": "alternative-reference",
            "Retry-After": "60",
          },
        });
      state.set({
        ...state.get(),
        alternatives: [{ ...initial, title: "Updated option" }],
      });
      await route.fulfill({ json: {} });
    });
    await open(page);
    await page.getByRole("button", { name: "Edit alternative" }).click();
    await page.getByLabel("Alternative title").fill("Updated option");
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "alternative-reference",
    );
    await expect(page.getByRole("alert")).not.toContainText("SECRET_INPUT");
    await expect(page.getByLabel("Alternative title")).toHaveValue(
      "Updated option",
    );
    if (status === 429)
      await expect(page.getByRole("alert")).toContainText("1 minute");
    fail = false;
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByRole("status")).toHaveText("Alternative updated.");
  });
}

for (const status of [409, 404, 0, 503]) {
  test(`save ${status || "network failure"} requires a reload before another mutation`, async ({
    page,
  }) => {
    const state = await setup(page);
    let writes = 0;
    await page.route("**/api/decisions/*/alternatives", (route) => {
      writes++;
      if (status === 409) state.set({ ...state.get(), status: "in_review" });
      return status ? route.fulfill({ status, json: {} }) : route.abort();
    });
    await open(page);
    await page
      .getByRole("button", { name: "Add alternative", exact: true })
      .click();
    await page.getByLabel("Alternative title").fill("Another option");
    await page
      .getByLabel("Description", { exact: true })
      .fill(initial.description);
    await page.getByRole("button", { name: "Save alternative" }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page.getByLabel("Alternative title")).toHaveValue(
      "Another option",
    );
    await expect(
      page.getByRole("button", { name: "Save alternative" }),
    ).toBeDisabled();
    if (status === 0 || status === 503)
      await expect(
        page.getByText(/Your change may already have been saved/),
      ).toBeVisible();
    expect(writes).toBe(1);
    await page.getByRole("button", { name: "Reload saved record" }).click();
    await expect(
      page.getByRole("heading", { name: initial.title, exact: true }),
    ).toBeVisible();
    if (status === 409)
      await expect(
        page.getByRole("button", { name: "Add alternative", exact: true }),
      ).toHaveCount(0);
    else
      await expect(
        page.getByRole("button", { name: "Add alternative", exact: true }),
      ).toBeEnabled();
  });
}

test("successful write followed by failed record refresh offers only a read retry", async ({
  page,
}) => {
  await setup(page);
  let changed = false,
    failRead = true,
    writes = 0;
  await page.route("**/api/decisions/*/record", (route) =>
    route.fulfill(
      changed && failRead
        ? { status: 503, json: {} }
        : {
            json: {
              ...record,
              alternatives: [
                {
                  ...initial,
                  title: changed ? "Updated option" : initial.title,
                },
              ],
            },
          },
    ),
  );
  await page.route("**/api/decisions/*/alternatives/*", (route) => {
    changed = true;
    writes++;
    return route.fulfill({ json: {} });
  });
  await open(page);
  await page.getByRole("button", { name: "Edit alternative" }).click();
  await page.getByLabel("Alternative title").fill("Updated option");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status")).toContainText("Alternative updated.");
  await expect(
    page.getByRole("heading", { name: "Let’s reload the record." }),
  ).toBeVisible();
  failRead = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { name: "Updated option" }),
  ).toBeVisible();
  expect(writes).toBe(1);
});

test("all non-draft statuses keep alternatives readable without editing controls", async ({
  page,
}) => {
  const state = await setup(page);
  for (const status of ["in_review", "decided", "cancelled", "superseded"]) {
    state.set({ ...state.get(), status });
    await open(page);
    await expect(page.getByText(/Alternatives are read-only/)).toBeVisible();
    await expect(
      page.getByRole("heading", { name: initial.title }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: /Add alternative|Edit alternative|Remove alternative/,
      }),
    ).toHaveCount(0);
  }
});

test("session expiration during a write removes the editor and requests sign-in", async ({
  page,
}) => {
  await setup(page);
  await page.route("**/api/decisions/*/alternatives/*", (route) =>
    route.fulfill({ status: 401, json: {} }),
  );
  await open(page);
  await page.getByRole("button", { name: "Edit alternative" }).click();
  await page.getByLabel("Alternative title").fill("Private unsaved option");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Alternative title")).toHaveCount(0);
});
