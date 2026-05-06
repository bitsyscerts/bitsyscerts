import { beforeEach, describe, expect, it, vi } from "vitest";
import { useStats } from "@/hooks/useStats";

const mockUseQuery = vi.fn<(options: unknown) => { fetchStatus: string }>();

vi.mock("@tanstack/react-query", () => ({
  useQuery: (options: unknown) => mockUseQuery(options),
}));

vi.mock("@/services/statsService", () => ({
  getStats: vi.fn().mockResolvedValue({
    total_hostnames: 1,
    total_certificates: 2,
    total_logs: 3,
    storage: { total_size_pretty: "1 MB", tables: [] },
    logs: [],
  }),
  STATS_QUERY_KEYS: { stats: () => ["stats"] },
}));

beforeEach(() => {
  mockUseQuery.mockReturnValue({ fetchStatus: "fetching" });
});

describe("useStats", () => {
  it("returns a query result object", () => {
    const result = useStats();
    expect(result.fetchStatus).toBe("fetching");
  });

  it("configures resilient polling behavior", () => {
    useStats(5_000);
    expect(mockUseQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        refetchInterval: 5_000,
        refetchIntervalInBackground: true,
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
        refetchOnMount: "always",
      }),
    );
  });
});
