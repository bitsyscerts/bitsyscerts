import { describe, it, expect, vi } from "vitest";
import { getStats, STATS_QUERY_KEYS } from "@/services/statsService";

vi.mock("@/services/apiClient", () => ({
  apiFetch: vi.fn().mockResolvedValue({ ingestion: {}, storage: {}, logs: [] }),
}));

import { apiFetch } from "@/services/apiClient";
const mockApiFetch = vi.mocked(apiFetch);

describe("STATS_QUERY_KEYS", () => {
  it("returns a stable key array", () => {
    const key = STATS_QUERY_KEYS.stats();
    expect(key).toEqual(["stats"]);
  });
});

describe("getStats", () => {
  it("calls apiFetch with the stats path", async () => {
    await getStats();
    expect(mockApiFetch).toHaveBeenCalledWith("/v1/stats");
  });
});
