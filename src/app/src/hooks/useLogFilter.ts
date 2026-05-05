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

/**
 * Client-side filter for CT log entries. Filters by free-text query (any
 * searchable field) and by an explicit list of log states.
 */
export function useLogFilter(logs: LogStatsItem[]) {
  const [query, setQuery] = useState("");
  const [stateFilter, setStateFilter] = useState<string[]>([]);

  const filtered = useMemo(
    () =>
      logs.filter((log) => {
        const queryOk = query === "" || matchesQuery(log, query);
        const stateOk =
          stateFilter.length === 0 || stateFilter.includes(log.log_state);
        return queryOk && stateOk;
      }),
    [logs, query, stateFilter],
  );

  return { query, setQuery, stateFilter, setStateFilter, filtered };
}
