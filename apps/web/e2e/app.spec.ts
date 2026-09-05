import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("demo dashboard recalculates from a calm baseline", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Maya Restrepo" })).toBeVisible();
  await expect(page.getByText("Baseline resilience")).toBeVisible();
  await expect(page.getByText("2 active")).toBeVisible();

  await page.getByRole("button", { name: "Calm baseline" }).click();

  await expect(page.getByText("0 active")).toBeVisible();
  await expect(page.getByText("No severe-risk trigger in this run.")).toBeVisible();

  await page.getByRole("button", { name: /Medical expense/ }).click();

  await expect(page.getByText("1 active")).toBeVisible();
  await expect(page.getByRole("button", { name: /Medical expense/ })).toHaveAttribute(
    "aria-pressed",
    "true"
  );
});

test("primary pages have no automatically detectable accessibility violations", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const path of ["/", "/intake", "/chat"]) {
    await page.goto(path);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(results.violations, path).toEqual([]);
  }
});

test("mobile layouts do not overflow horizontally", async ({ page }) => {
  for (const path of ["/", "/intake", "/chat"]) {
    await page.goto(path);
    const widths = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(widths.content, path).toBeLessThanOrEqual(widths.viewport);
  }
});

test("chat exposes grounded score-planning prompts", async ({ page }) => {
  await page.goto("/chat");

  await expect(
    page.getByRole("button", { name: "What would it take to get my score to 70?" })
  ).toBeVisible();
  await expect(page.getByText("What we know about you")).toBeVisible();
});
