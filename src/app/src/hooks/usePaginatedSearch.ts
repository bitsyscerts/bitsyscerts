import { useEffect, useState } from "react";
import { useHostnameSearch } from "@/hooks/useHostnameSearch";
import type { HostnameSearchParams, HostnameListResponse } from "@/types";

const OVER_LIMIT = 10_001;

const MAX_DISPLAY_PAGES = 200;

export interface PaginatedSearchResult {
  data: HostnameListResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  currentPage: number;
  /** Number of pages we have cursors for (increases as user navigates). */
  knownPageCount: number;
  /**
   * Upfront page count derived from total_estimate / limit, capped at
   * MAX_DISPLAY_PAGES. Null until the first page response arrives.
   */
  estimatedPageCount: number | null;
  /** Cached total_estimate from the first page response. */
  totalEstimate: number | null;
  /** True when total_estimate >= 10,001 (API sentinel for "more than 10,000"). */
  isOverLimit: boolean;
  canGoPrev: boolean;
  canGoNext: boolean;
  goToPage: (page: number) => void;
  goNext: () => void;
  goPrev: () => void;
}

interface State {
  submittedQuery: string;
  pageIndex: number;
  cursorCache: (string | null)[];
  totalEstimate: number | null;
}

const initialState = (q: string): State => ({
  submittedQuery: q,
  pageIndex: 0,
  cursorCache: [null],
  totalEstimate: null,
});

/**
 * Wraps useHostnameSearch with cursor-cache pagination.
 *
 * Cursors are cached as the user navigates forward, allowing arbitrary
 * navigation to any previously visited page. Page state resets synchronously
 * when submittedQuery changes to avoid stale cursors reaching the API.
 */
export function usePaginatedSearch(
  buildParams: (cursor: string | null) => HostnameSearchParams,
  submittedQuery: string,
): PaginatedSearchResult {
  const [state, setState] = useState<State>(() => initialState(submittedQuery));

  // Synchronous derived-state reset when submittedQuery changes.
  // React allows setState-during-render for this pattern (derived state).
  let resolved = state;
  if (state.submittedQuery !== submittedQuery) {
    resolved = initialState(submittedQuery);
    setState(resolved);
  }

  const params = buildParams(resolved.cursorCache[resolved.pageIndex] ?? null);
  const query = useHostnameSearch(params);

  // Cache total_estimate from the first-page response.
  useEffect(() => {
    const est = query.data?.total_estimate;
    if (est == null) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState((prev) => {
      if (prev.submittedQuery !== submittedQuery || prev.totalEstimate != null)
        return prev;
      return { ...prev, totalEstimate: est };
    });
  }, [query.data?.total_estimate, submittedQuery]);

  // Extend cursor cache when a new next_cursor arrives.
  useEffect(() => {
    const next = query.data?.next_cursor;
    if (!next) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState((prev) => {
      if (prev.submittedQuery !== submittedQuery) return prev;
      if (prev.pageIndex + 1 < prev.cursorCache.length) return prev;
      return { ...prev, cursorCache: [...prev.cursorCache, next] };
    });
  }, [query.data?.next_cursor, submittedQuery]);

  const { pageIndex, cursorCache, totalEstimate } = resolved;
  const knownPageCount = cursorCache.length;
  const canGoNext = !!query.data?.next_cursor;
  const canGoPrev = pageIndex > 0;

  const estimatedPageCount: number | null =
    totalEstimate != null
      ? Math.min(
          Math.ceil(
            Math.min(totalEstimate, 10_000) / Math.max(params.limit, 1),
          ),
          MAX_DISPLAY_PAGES,
        )
      : null;

  function goToPage(page: number) {
    const idx = page - 1;
    if (idx >= 0 && idx < cursorCache.length) {
      setState((prev) => ({ ...prev, pageIndex: idx }));
    }
  }

  function goNext() {
    if (pageIndex + 1 < cursorCache.length) {
      setState((prev) => ({ ...prev, pageIndex: prev.pageIndex + 1 }));
    }
  }

  function goPrev() {
    if (pageIndex > 0) {
      setState((prev) => ({ ...prev, pageIndex: prev.pageIndex - 1 }));
    }
  }

  return {
    data: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    currentPage: pageIndex + 1,
    knownPageCount,
    estimatedPageCount,
    totalEstimate,
    isOverLimit: totalEstimate != null && totalEstimate >= OVER_LIMIT,
    canGoPrev,
    canGoNext,
    goToPage,
    goNext,
    goPrev,
  };
}
