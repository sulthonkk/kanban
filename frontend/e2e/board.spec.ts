import { expect, test } from "@playwright/test";
import { installMockApi } from "./mock-api";

test("supports the core board workflow", async ({ page }) => {
  await installMockApi(page);
  await page.goto("/");
  await expect(page.getByLabel("This week sprint overview")).toBeVisible();
  await page.getByLabel("Project title").fill("Launch Sprint");
  await expect(page.getByLabel("Project title")).toHaveValue("Launch Sprint");
  await expect(page.getByLabel("Backlog column")).toContainText("Refresh the onboarding");
  await page.getByRole("button", { name: "Rename Backlog" }).click();
  await page.getByLabel("Column name").fill("Ideas");
  await page.getByLabel("Column name").press("Enter");
  await expect(page.getByLabel("Ideas column")).toBeVisible();
  const ready = page.getByLabel("Ready column");
  const movingCard = page.getByRole("button", { name: /Refresh the onboarding/ }).first();
  await movingCard.scrollIntoViewIfNeeded();
  await ready.scrollIntoViewIfNeeded();
  const cardBox = await movingCard.boundingBox();
  const readyBox = await ready.boundingBox();
  if (!cardBox || !readyBox) throw new Error("Expected drag source and destination to be visible");
  await page.mouse.move(cardBox.x + cardBox.width / 2, cardBox.y + cardBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(readyBox.x + readyBox.width / 2, readyBox.y + readyBox.height / 2, { steps: 12 });
  await page.mouse.up();
  await expect(ready).toContainText("Refresh the onboarding");
  await expect(page.getByLabel("Ideas column")).not.toContainText("Refresh the onboarding");
  await ready.getByRole("button", { name: "+ Add a card" }).click();
  await ready.getByLabel("Card title").fill("Check release notes");
  await ready.getByLabel("Card details").fill("Proof the final version.");
  await ready.getByRole("button", { name: "Add card" }).click();
  await expect(ready).toContainText("Check release notes");
  // Persisted across a reload (the mock store survives navigation).
  await page.reload();
  await expect(ready).toContainText("Check release notes");
  await ready.getByRole("button", { name: "Delete Check release notes", exact: true }).click();
  await expect(ready).not.toContainText("Check release notes");
});