import type { StatsResponse } from "@/types";

type StatsModeSource = Pick<
  StatsResponse,
  "backfill_state" | "backfill_ranges"
>;

export function isPerLogPrimaryMode(stats: StatsModeSource): boolean {
  const backfillState = stats.backfill_state;
  if (backfillState?.is_primary) {
    return true;
  }
  if (backfillState?.dispatch_mode) {
    return backfillState.dispatch_mode === "per-log";
  }

  const backfillRanges = stats.backfill_ranges;
  if (backfillRanges.is_primary) {
    return false;
  }

  return backfillRanges.dispatch_mode === "per-log";
}
