import { useQuery } from "@tanstack/react-query";
import { getStats, STATS_QUERY_KEYS } from "@/services/statsService";
import type { StatsResponse } from "@/types";

/**
 * TanStack Query wrapper for the stats endpoint.
 * @param refetchInterval - milliseconds between automatic refetches (default 60 s).
 * @param refetchIntervalInBackground - whether to poll when the tab is hidden (default false).
 */
export function useStats(
  refetchInterval = 60_000,
  refetchIntervalInBackground = false,
) {
  return useQuery<StatsResponse>({
    queryKey: STATS_QUERY_KEYS.stats(),
    queryFn: getStats,
    refetchInterval,
    refetchIntervalInBackground,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    refetchOnMount: "always",
  });
}
