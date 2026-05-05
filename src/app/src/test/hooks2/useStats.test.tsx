import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useStats } from "@/hooks/useStats";

vi.mock("@/services/statsService", () => ({
  getStats: vi
    .fn()
    .mockResolvedValue({
      total_hostnames: 1,
      total_certificates: 2,
      total_logs: 3,
      storage: { total_size_pretty: "1 MB", tables: [] },
      logs: [],
    }),
  STATS_QUERY_KEYS: { stats: () => ["stats"] },
}));

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useStats", () => {
  it("returns a query result object", () => {
    const { result } = renderHook(() => useStats(), { wrapper });
    // Query is not idle — it should be fetching
    expect(result.current.fetchStatus).toBe("fetching");
  });

  it("accepts custom refetchInterval", () => {
    const { result } = renderHook(() => useStats(5_000), { wrapper });
    expect(result.current).toBeDefined();
  });
});
