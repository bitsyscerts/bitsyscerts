import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/hooks/useHostnameSearch", () => ({
  useHostnameSearch: vi.fn(),
}));

import { useHostnameSearch } from "@/hooks/useHostnameSearch";
import { usePaginatedSearch } from "@/hooks/usePaginatedSearch";
import type { HostnameListResponse } from "@/types";

const mockUseHostnameSearch = vi.mocked(useHostnameSearch);

const EMPTY_RESPONSE: HostnameListResponse = {
  items: [],
  next_cursor: null,
  total_returned: 0,
  total_estimate: 0,
};

const PAGE1_RESPONSE: HostnameListResponse = {
  items: [],
  next_cursor: "cursor-page2",
  total_returned: 50,
  total_estimate: 500,
};

const PAGE2_RESPONSE: HostnameListResponse = {
  items: [],
  next_cursor: null,
  total_returned: 20,
  total_estimate: 500,
};

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const buildParams = (cursor: string | null) => ({
  q: "example.com",
  recursive: true,
  depth: null,
  sort: "not_before_desc" as const,
  limit: 50,
  cursor,
  include_certs: false,
});

describe("usePaginatedSearch initial state", () => {
  it("starts at page 1 with no prev/next when data is empty", () => {
    mockUseHostnameSearch.mockReturnValue({
      data: EMPTY_RESPONSE,
      isLoading: false,
      isError: false,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useHostnameSearch>);

    const { result } = renderHook(
      () => usePaginatedSearch(buildParams, "example.com"),
      { wrapper },
    );

    expect(result.current.currentPage).toBe(1);
    expect(result.current.canGoPrev).toBe(false);
    expect(result.current.canGoNext).toBe(false);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.isError).toBe(false);
  });

  it("reflects isLoading from useHostnameSearch", () => {
    mockUseHostnameSearch.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      fetchStatus: "fetching",
    } as unknown as ReturnType<typeof useHostnameSearch>);

    const { result } = renderHook(
      () => usePaginatedSearch(buildParams, "example.com"),
      { wrapper },
    );

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
  });

  it("reflects isError from useHostnameSearch", () => {
    mockUseHostnameSearch.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useHostnameSearch>);

    const { result } = renderHook(
      () => usePaginatedSearch(buildParams, "example.com"),
      { wrapper },
    );

    expect(result.current.isError).toBe(true);
  });

  it("exposes estimatedPageCount once data has total_estimate", () => {
    mockUseHostnameSearch.mockReturnValue({
      data: { items: [], next_cursor: null, total_estimate: 150 },
      isLoading: false,
      isError: false,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useHostnameSearch>);

    const { result } = renderHook(
      () => usePaginatedSearch(buildParams, "example.com"),
      { wrapper },
    );

    // estimatedPageCount = ceil(150 / 50) = 3
    expect(result.current.estimatedPageCount).toBe(3);
  });

  it("isOverLimit when total_estimate >= 10001", () => {
    mockUseHostnameSearch.mockReturnValue({
      data: { items: [], next_cursor: null, total_estimate: 10_001 },
      isLoading: false,
      isError: false,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useHostnameSearch>);

    const { result } = renderHook(
      () => usePaginatedSearch(buildParams, "example.com"),
      { wrapper },
    );

    expect(result.current.isOverLimit).toBe(true);
  });
});

describe("usePaginatedSearch navigation", () => {
  it("canGoNext when next_cursor is non-null", () => {
    mockUseHostnameSearch.mockReturnValue({
      data: PAGE1_RESPONSE,
      isLoading: false,
      isError: false,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useHostnameSearch>);

    const { result } = renderHook(
      () => usePaginatedSearch(buildParams, "example.com"),
      { wrapper },
    );

    expect(result.current.canGoNext).toBe(true);
  });

  it("goNext advances to page 2", () => {
    mockUseHostnameSearch.mockReturnValue({
      data: PAGE1_RESPONSE,
      isLoading: false,
      isError: false,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useHostnameSearch>);

    const { result } = renderHook(
      () => usePaginatedSearch(buildParams, "example.com"),
      { wrapper },
    );

    // After goNext, the cursor cache gets extended and goNext can advance
    act(() => {
      result.current.goNext();
    });
    expect(result.current.currentPage).toBe(2);
  });

  it("goPrev does nothing on page 1", () => {
    mockUseHostnameSearch.mockReturnValue({
      data: PAGE1_RESPONSE,
      isLoading: false,
      isError: false,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useHostnameSearch>);

    const { result } = renderHook(
      () => usePaginatedSearch(buildParams, "example.com"),
      { wrapper },
    );

    act(() => {
      result.current.goPrev();
    });
    expect(result.current.currentPage).toBe(1);
  });

  it("goPrev returns to page 1 after goNext", () => {
    mockUseHostnameSearch
      .mockReturnValueOnce({
        data: PAGE1_RESPONSE,
        isLoading: false,
        isError: false,
        fetchStatus: "idle",
      } as unknown as ReturnType<typeof useHostnameSearch>)
      .mockReturnValue({
        data: PAGE2_RESPONSE,
        isLoading: false,
        isError: false,
        fetchStatus: "idle",
      } as unknown as ReturnType<typeof useHostnameSearch>);

    const { result } = renderHook(
      () => usePaginatedSearch(buildParams, "example.com"),
      { wrapper },
    );

    act(() => {
      result.current.goNext();
    });
    expect(result.current.currentPage).toBe(2);
    expect(result.current.canGoPrev).toBe(true);

    act(() => {
      result.current.goPrev();
    });
    expect(result.current.currentPage).toBe(1);
  });

  it("goToPage navigates to a valid cached page", () => {
    mockUseHostnameSearch.mockReturnValue({
      data: PAGE1_RESPONSE,
      isLoading: false,
      isError: false,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useHostnameSearch>);

    const { result } = renderHook(
      () => usePaginatedSearch(buildParams, "example.com"),
      { wrapper },
    );

    // First advance so page 2 cursor is cached
    act(() => {
      result.current.goNext();
    });
    act(() => {
      result.current.goToPage(1);
    });
    expect(result.current.currentPage).toBe(1);
  });

  it("resets state when submittedQuery changes", () => {
    mockUseHostnameSearch.mockReturnValue({
      data: PAGE1_RESPONSE,
      isLoading: false,
      isError: false,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useHostnameSearch>);

    let query = "example.com";
    const { result, rerender } = renderHook(
      () => usePaginatedSearch(buildParams, query),
      { wrapper },
    );

    act(() => {
      result.current.goNext();
    });
    expect(result.current.currentPage).toBe(2);

    query = "new-query.com";
    rerender();

    expect(result.current.currentPage).toBe(1);
  });
});
