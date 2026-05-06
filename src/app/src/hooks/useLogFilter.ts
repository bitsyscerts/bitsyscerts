import { useMemo, useState } from "react";
import type { LogStatsItem } from "@/types";

const SEARCHABLE_FIELDS: (keyof LogStatsItem)[] = [
  "description",
  "url",
  "log_id",
  "log_state",
];

function matchesQuery(log: LogStatsItem, q: string): boolean {
  const lower = q.toLowerCase();
  return SEARCHABLE_FIELDS.some((field) => {
    const val = log[field];
    return val != null && String(val).toLowerCase().includes(lower);
  });
}

function completionScore(log: LogStatsItem): number {
  return log.backfill_complete_pct ?? -1;
}

function tailPositionScore(log: LogStatsItem): number {
  return log.tail_position ?? -1;
}

function isSynced(log: LogStatsItem): boolean {
  return (log.backfill_complete_pct ?? -1) >= 100;
}

/**
 * Client-side filter for CT log entries.
 *
 * - Defaults to only "usable" logs.
 * - Hides fully synced logs by default.
 * - Filters by free-text query (any searchable field) and selected states.
 * - Orders logs from most-complete to least-complete by backfill percentage.
 */
export function useLogFilter(logs: LogStatsItem[]) {
  const [query, setQuery] = useState("");
  const [stateFilter, setStateFilter] = useState<string[]>(["usable"]);
  const [hideSynced, setHideSynced] = useState(true);

  const filtered = useMemo(
    () =>
      logs
        .filter((log) => {
          const queryOk = query === "" || matchesQuery(log, query);
          const stateOk =
            stateFilter.length === 0 || stateFilter.includes(log.log_state);
          const syncedOk = !hideSynced || !isSynced(log);
          return queryOk && stateOk && syncedOk;
        })
        .sort((a, b) => {
          const completionDiff = completionScore(b) - completionScore(a);
          if (completionDiff !== 0) return completionDiff;

          const tailDiff = tailPositionScore(b) - tailPositionScore(a);
          if (tailDiff !== 0) return tailDiff;

          return a.description.localeCompare(b.description);
        }),
    [logs, query, stateFilter, hideSynced],
  );

  return {
    query,
    setQuery,
    stateFilter,
    setStateFilter,
    hideSynced,
    setHideSynced,
    filtered,
  };
}
