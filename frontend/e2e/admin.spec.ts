/**
 * Admin panel walkthrough (video + numbered screenshots, continuing the main walkthrough's numbering).
 *   E2E_ADMIN_EMAIL=... E2E_ADMIN_PASSWORD=... E2E_USER_EMAIL=... E2E_USER_PASSWORD=... npx playwright test e2e/admin.spec.ts
 * Read-only by design: config edits are shown as an unsaved draft and discarded, so production settings never change.
 */
import { test, expect, Page } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const OUT = path.resolve(process.cwd(), "../app_screenshots_screen_recording");
let step = 16;

async function shot(page: Page, name: string, fullPage = false) {
  step += 1;
  await page.screenshot({ path: path.join(OUT, `${String(step).padStart(2, "0")}_${name}.png`), fullPage });
}

async function signIn(page: Page, email: string, password: string, next = "/chat") {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(new RegExp(next.replace("/", "\\/")), { timeout: 60_000 });
}

test("admin panel walkthrough", async ({ page }) => {
  fs.mkdirSync(OUT, { recursive: true });
  const email = process.env.E2E_ADMIN_EMAIL!;
  const password = process.env.E2E_ADMIN_PASSWORD!;

  // admin link appears in the research chat only for admins
  await signIn(page, email, password, "/chat");
  await expect(page.getByTestId("admin-link")).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(1200);
  await shot(page, "admin_link_in_chat_toolbar");

  // overview
  await page.getByTestId("admin-link").click();
  await page.waitForURL(/\/admin/);
  await expect(page.getByTestId("admin-overview")).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(2500);
  await shot(page, "admin_overview_kpis_and_charts");
  await page.getByRole("button", { name: "30 days" }).click();
  await page.waitForTimeout(2500);
  await shot(page, "admin_overview_usage_by_model_and_node", true);

  // models & safety: show an unsaved draft (kill switch + temperature), then discard
  await page.getByTestId("tab-models").click();
  await expect(page.getByTestId("admin-models")).toBeVisible();
  await page.waitForTimeout(1500);
  await shot(page, "admin_models_and_safety_config");
  await page.getByLabel(/Pause all research requests/).check();
  await page.getByPlaceholder(/Reason for change/).pressSequentially("Demo: planned GPU maintenance window", { delay: 15 });
  await page.waitForTimeout(800);
  await shot(page, "admin_kill_switch_draft_with_reason");
  await page.getByRole("button", { name: "Discard" }).click();
  await page.getByPlaceholder(/Reason for change/).fill("");

  // agents & knowledge
  await page.getByTestId("tab-knowledge").click();
  await expect(page.getByTestId("admin-knowledge")).toBeVisible();
  await page.waitForTimeout(2500);
  await shot(page, "admin_agent_permissions_and_rag_index", true);

  // users & roles (emails masked by default)
  await page.getByTestId("tab-users").click();
  await expect(page.getByTestId("admin-users")).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(1500);
  await shot(page, "admin_users_and_roles_masked_pii");

  // audit log, filtered
  await page.getByTestId("tab-audit").click();
  await expect(page.getByTestId("admin-audit")).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(1200);
  await shot(page, "admin_audit_log_all_events");
  await page.getByLabel("Filter by event").selectOption("guard_input");
  await page.waitForTimeout(2000);
  await shot(page, "admin_audit_log_guardrail_events");
});

test("non-admin is refused by the server", async ({ page }) => {
  await signIn(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!, "/chat");
  await expect(page.getByTestId("admin-link")).toHaveCount(0);
  await page.goto("/admin");
  await expect(page.getByText("Admin access required")).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(800);
  step = 25;
  await shot(page, "admin_non_admin_refused_403");
});
