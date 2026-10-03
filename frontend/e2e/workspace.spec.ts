import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Open navigation" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("navigation").getByRole("link", { name }).click();
}
async function accessible(page: Page) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(
      document.getAnimations().map((animation) => animation.finished),
    );
  });
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    scan.violations.map(({ id, nodes }) => ({
      id,
      nodes: nodes.map(({ target, failureSummary }) => ({
        target,
        failureSummary,
      })),
    })),
  ).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
}

test("reviews evidence, edits rationale, finalizes the preview, and resets on refresh", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/preview");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Every decision.",
  );
  await accessible(page);
  await page
    .getByRole("button", { name: /Cooling system specification/ })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText("page 12");
  await accessible(page);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  // Programmatic dialog openers restore focus to the control that opened them.
  await expect(
    page.getByRole("button", { name: /Cooling system specification/ }),
  ).toBeFocused();
  await page.getByRole("radio", { name: /Keep the current limit/ }).check();
  await page
    .getByRole("button", { name: "Review decision", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "The linked evidence supports alternative B",
  );
  await page.getByRole("button", { name: "Keep reviewing" }).click();
  await page.getByRole("radio", { name: /Reduce the operating limit/ }).check();
  await page.getByRole("button", { name: "Edit rationale" }).click();
  await page.getByLabel("Decision rationale").fill("Short");
  await expect(
    page.getByRole("button", { name: "Update preview" }),
  ).toBeDisabled();
  await page
    .getByLabel("Decision rationale")
    .fill(
      "Reduce the operating limit because both source excerpts support additional headroom.",
    );
  await page.getByRole("button", { name: "Update preview" }).click();
  await expect(page.locator(".rationale-copy")).toContainText(
    "both source excerpts",
  );
  await page
    .getByRole("button", { name: "Review decision", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Finalize preview", exact: true })
    .click();
  await expect(
    page.getByText("Decided · preview", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Edit rationale" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: /History/ }).click();
  await expect(
    page.getByRole("heading", { name: "Decision finalized in preview" }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText("In review", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("filters documents and searches excerpts with URL-backed navigation", async ({
  page,
}) => {
  await page.goto("/preview");
  await navigate(page, "Documents");
  await page.getByRole("button", { name: "Review note", exact: true }).click();
  await expect(page.locator(".document-row")).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "Open Pressure transient review" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "All documents", exact: true })
    .click();
  await expect(page.locator(".document-row")).toHaveCount(3);
  await accessible(page);
  await page
    .getByRole("button", { name: "Open Electrical isolation procedure" })
    .click();
  await expect(page.getByRole("dialog")).toContainText("ENG-EL-008");
  await page.getByRole("button", { name: "Close dialog" }).click();
  await navigate(page, "Search");
  await expect(page.locator(".search-result")).toHaveCount(2);
  await accessible(page);
  await page
    .getByRole("button", { name: "Electrical isolation", exact: true })
    .click();
  await expect(page.locator(".search-result")).toHaveCount(1);
  await expect(page.getByLabel("Search sample library")).toHaveValue(
    "electrical isolation",
  );
  await page.goBack();
  await expect(page.getByLabel("Search sample library")).toHaveValue(
    "cooling pressure",
  );
  await page.getByLabel("Search sample library").fill("unobtainium");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No matching passages." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Search cooling" }).click();
  await expect(page.locator(".search-result")).toHaveCount(2);
  await page
    .getByRole("button", { name: "Inspect source excerpt" })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Cooling system specification",
  );
});

test("explains the preview and recovers from unknown routes", async ({
  page,
}) => {
  await page.goto("/preview/missing-page");
  await page
    .getByRole("link", { name: "Return to the decision workspace" })
    .click();
  await page.getByRole("button", { name: "Interactive preview" }).click();
  await expect(page.getByRole("dialog")).toContainText("no embedding requests");
  await accessible(page);
  await page.getByRole("button", { name: "Explore the workspace" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
});
