/**
 * MCP server capture via the in-app MCP console (/developers), against production.
 *   E2E_USER_EMAIL=... E2E_USER_PASSWORD=... npx playwright test e2e/mcp.spec.ts
 */
import { test, expect, Page } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(process.cwd(), "../app_screenshots_screen_recording");
let step = 27;

async function shot(page: Page, name: string, fullPage = false) {
  step += 1;
  await page.screenshot({ path: path.join(OUT, `${String(step).padStart(2, "0")}_${name}.png`), fullPage });
}

async function runTool(page: Page, name: string) {
  await page.getByTestId(`tool-${name}`).click();
  await page.waitForTimeout(600);
  await page.getByTestId("mcp-run").click();
  await expect(page.getByTestId("mcp-result")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("mcp-run")).toBeEnabled({ timeout: 120_000 });
  await page.waitForTimeout(900);
}

test("MCP server via the developer console", async ({ page }) => {
  await page.goto("/login?next=/chat");
  await page.getByLabel("Work email").fill(process.env.E2E_USER_EMAIL!);
  await page.getByLabel("Password").fill(process.env.E2E_USER_PASSWORD!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/chat/, { timeout: 60_000 });
  await expect(page.getByTestId("developers-link")).toBeVisible({ timeout: 30_000 });

  await page.getByTestId("developers-link").click();
  await page.waitForURL(/\/developers/);
  await expect(page.getByTestId("mcp-endpoint")).toBeVisible();
  await page.waitForTimeout(1000);
  await shot(page, "mcp_console_endpoint_and_session");

  // 1. no token -> 401 + WWW-Authenticate challenge
  await page.getByTestId("mcp-unauth").click();
  await expect(page.getByTestId("mcp-unauth-result")).toContainText("401", { timeout: 60_000 });
  await page.waitForTimeout(800);
  await shot(page, "mcp_no_token_401_challenge");

  // 2. OAuth metadata -> initialize -> tools/list
  await page.getByTestId("mcp-connect").click();
  await expect(page.getByTestId("mcp-tools")).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(1200);
  await shot(page, "mcp_connected_tools_list", true);
  await page.waitForTimeout(4500); // let the "Connected" toast clear

  // 3. tools/call
  await runTool(page, "patent_landscape");
  await shot(page, "mcp_tool_call_patent_landscape");
  await runTool(page, "opportunity_score");
  await shot(page, "mcp_tool_call_opportunity_score_ml");
  await runTool(page, "my_reports");
  await page.getByTestId("mcp-wire").scrollIntoViewIfNeeded();
  await page.waitForTimeout(800);
  await shot(page, "mcp_tool_call_my_reports_and_wire_log", true);
});
