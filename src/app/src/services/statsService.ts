import { apiFetch } from "./apiClient";
import type { StatsResponse } from "@/types";

export const STATS_QUERY_KEYS = {
  stats: () => ["stats"] as const,
} as const;

export async function getStats(): Promise<StatsResponse> {
  return apiFetch<StatsResponse>("/v1/stats");
}
