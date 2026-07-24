import { describe, expect, it } from "vitest";
import { dailyQuote, getSprintMetrics } from "./sprint";

describe("sprint metrics", () => {
  it("calculates sprint progress and remaining days", () => {
    const metrics = getSprintMetrics("2026-07-21", "2026-07-28", new Date("2026-07-23T12:00:00"));
    expect(metrics.currentDay).toBe(3);
    expect(metrics.progress).toBe(43);
    expect(metrics.daysRemaining).toBe(5);
  });
  it("never reports negative remaining days and marks completed sprints", () => {
    const metrics = getSprintMetrics("2026-07-21", "2026-07-28", new Date("2026-07-30T12:00:00"));
    expect(metrics.daysRemaining).toBe(0);
    expect(metrics.status).toBe("Completed");
  });
  it("selects the same quote for the same calendar day", () => {
    expect(dailyQuote(new Date("2026-07-21T08:00:00"))).toBe(dailyQuote(new Date("2026-07-21T20:00:00")));
  });
});
