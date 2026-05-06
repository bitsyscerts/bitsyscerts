import { useQuery } from "@tanstack/react-query";
import { getStats, STATS_QUERY_KEYS } from "@/services/statsService";
import type { StatsResponse } from "@/types";

/**
 * TanStack Query wrapper for the stats endpoint.
 * @param refetchInterval - milliseconds between automatic refetches (default 60 s).
 */
export function useStats(refetchInterval = 60_000) {
  return useQuery<StatsResponse>({
    queryKey: STATS_QUERY_KEYS.stats(),
    queryFn: getStats,
    refetchInterval,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    refetchOnMount: "always",
  });
}
