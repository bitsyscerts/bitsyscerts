import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLogFilter } from "@/hooks/useLogFilter";
import type { LogStatsItem } from "@/types";

function makeLog(overrides: Partial<LogStatsItem> = {}): LogStatsItem {
  return {
    log_id: "log-1",
    description: "Test Log",
    url: "https://ct.example.com",
    log_state: "usable",
    tail_position: null,
    backfill_complete_pct: null,
    last_tail_sync: null,
    ...overrides,
  };
}

const LOGS: LogStatsItem[] = [
  makeLog({ log_id: "1", description: "Google Argon", log_state: "usable" }),
  makeLog({
    log_id: "2",
    description: "Cloudflare Nimbus",
    log_state: "readonly",
  }),
  makeLog({ log_id: "3", description: "DigiCert Yeti", log_state: "retired" }),
  makeLog({
    log_id: "4",
    description: "Let's Encrypt Oak",
    log_state: "pending",
  }),
];

describe("useLogFilter", () => {
  it("returns all logs when query is empty and no state filter", () => {
    const { result } = renderHook(() => useLogFilter(LOGS));
    expect(result.current.filtered).toHaveLength(4);
  });

  it("filters by description (case-insensitive)", () => {
    const { result } = renderHook(() => useLogFilter(LOGS));
    act(() => {
      result.current.setQuery("google");
    });
    expect(result.current.filtered).toHaveLength(1);
    expect(result.current.filtered[0].log_id).toBe("1");
  });

  it("filters by log_state field", () => {
    const { result } = renderHook(() => useLogFilter(LOGS));
    act(() => {
      result.current.setQuery("usable");
    });
    expect(result.current.filtered[0].log_state).toBe("usable");
  });

  it("state filter: shows only selected states", () => {
    const { result } = renderHook(() => useLogFilter(LOGS));
    act(() => {
      result.current.setStateFilter(["usable", "retired"]);
    });
    expect(result.current.filtered).toHaveLength(2);
    expect(result.current.filtered.map((l) => l.log_state)).toEqual(
      expect.arrayContaining(["usable", "retired"]),
    );
  });

  it("state filter: empty array shows all logs", () => {
    const { result } = renderHook(() => useLogFilter(LOGS));
    act(() => {
      result.current.setStateFilter([]);
    });
    expect(result.current.filtered).toHaveLength(4);
  });

  it("combines text query and state filter", () => {
    const { result } = renderHook(() => useLogFilter(LOGS));
    act(() => {
      result.current.setQuery("nimbus");
      result.current.setStateFilter(["readonly"]);
    });
    expect(result.current.filtered).toHaveLength(1);
    expect(result.current.filtered[0].log_id).toBe("2");
  });

  it("returns empty array when nothing matches", () => {
    const { result } = renderHook(() => useLogFilter(LOGS));
    act(() => {
      result.current.setQuery("zzz-no-match");
    });
    expect(result.current.filtered).toHaveLength(0);
  });

  it("exposes query and stateFilter values", () => {
    const { result } = renderHook(() => useLogFilter(LOGS));
    act(() => {
      result.current.setQuery("test");
      result.current.setStateFilter(["usable"]);
    });
    expect(result.current.query).toBe("test");
    expect(result.current.stateFilter).toEqual(["usable"]);
  });
});
