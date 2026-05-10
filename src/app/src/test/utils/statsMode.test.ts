import { describe, expect, it } from "vitest";

import { isPerLogPrimaryMode } from "@/utils/statsMode";

describe("isPerLogPrimaryMode", () => {
  it("prefers explicit per-log primary metadata from backfill_state", () => {
    expect(
      isPerLogPrimaryMode({
        backfill_state: {
          total_logs: 1,
          pending: 0,
          claimed: 0,
          processing: 1,
          retrying: 0,
          rate_limited: 0,
          paused: 0,
          complete: 0,
          error: 0,
          stale: 0,
          items: [],
          dispatch_mode: "per-log",
          is_primary: true,
        },
        backfill_ranges: {
          pending: 0,
          in_progress: 0,
          stale_in_progress: 0,
          completed: 10,
          failed: 5,
          dispatch_mode: "per-log",
          is_primary: false,
        },
      }),
    ).toBe(true);
  });

  it("falls back to backfill_ranges metadata for live per-log responses", () => {
    expect(
      isPerLogPrimaryMode({
        backfill_state: null,
        backfill_ranges: {
          pending: 0,
          in_progress: 0,
          stale_in_progress: 0,
          completed: 10,
          failed: 5,
          dispatch_mode: "per-log",
          is_primary: false,
        },
      }),
    ).toBe(true);
  });

  it("returns false when legacy-ranges are marked primary", () => {
    expect(
      isPerLogPrimaryMode({
        backfill_state: null,
        backfill_ranges: {
          pending: 0,
          in_progress: 1,
          stale_in_progress: 0,
          completed: 10,
          failed: 1,
          dispatch_mode: "legacy-ranges",
          is_primary: true,
        },
      }),
    ).toBe(false);
  });
});
