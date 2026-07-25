import { expect, test } from "@playwright/test";
import { installMockApi, installMockApiUnauthorized } from "./mock-api";

test("signs the user out and returns to the login page", async ({ page }) => {
  await installMockApi(page);
  await page.goto("/");
  await expect(page.getByLabel("Backlog column")).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();

  await page.waitForURL("**/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("redirects to login when the board call is unauthorized", async ({ page }) => {
  await installMockApiUnauthorized(page);
  await page.goto("/");

  await page.waitForURL("**/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});