import { test, expect } from "@playwright/test";

test.use({ video: "off" });

test("landing, protected route, signup and chat shell", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Revive approved molecules.")).toBeVisible();

  // /chat is protected by middleware
  await page.goto("/chat");
  await expect(page).toHaveURL(/\/login/);

  await page.goto("/signup");
  await page.getByLabel("Work email").fill(`smoke.${Date.now()}@repurpora.app`);
  await page.getByLabel("Password").fill("Repurpora!2026");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(/\/chat/, { timeout: 60_000 });
  await expect(page.getByTestId("sample-prompts")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Agent server unreachable/)).toHaveCount(0);
});
