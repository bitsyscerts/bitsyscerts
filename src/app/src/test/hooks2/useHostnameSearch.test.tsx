import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useHostnameSearch } from "@/hooks/useHostnameSearch";

vi.mock("@/services/hostnamesService", () => ({
  searchHostnames: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
  HOSTNAME_QUERY_KEYS: { search: (p: unknown) => ["hostnames", "search", p] },
}));

const BASE_PARAMS = {
  q: "example.com",
  recursive: true,
  depth: null,
  sort: "not_before_desc" as const,
  limit: 50,
  cursor: null,
  include_certs: false,
};

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useHostnameSearch", () => {
  it("is disabled when q is empty", () => {
    const { result } = renderHook(
      () => useHostnameSearch({ ...BASE_PARAMS, q: "" }),
      { wrapper },
    );
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("is disabled when q is whitespace only", () => {
    const { result } = renderHook(
      () => useHostnameSearch({ ...BASE_PARAMS, q: "   " }),
      { wrapper },
    );
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("is enabled when q is non-empty", () => {
    const { result } = renderHook(() => useHostnameSearch(BASE_PARAMS), {
      wrapper,
    });
    expect(result.current.fetchStatus).not.toBe("idle");
  });
});
