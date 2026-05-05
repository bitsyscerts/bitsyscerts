import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSearchState } from "@/hooks/useSearchState";

describe("useSearchState", () => {
  it("starts with empty queries and default options", () => {
    const { result } = renderHook(() => useSearchState());
    expect(result.current.query).toBe("");
    expect(result.current.submittedQuery).toBe("");
    expect(result.current.options.recursive).toBe(true);
  });

  it("setQuery updates query without changing submittedQuery", () => {
    const { result } = renderHook(() => useSearchState());
    act(() => {
      result.current.setQuery("hello");
    });
    expect(result.current.query).toBe("hello");
    expect(result.current.submittedQuery).toBe("");
  });

  it("submitSearch commits query to submittedQuery", () => {
    const { result } = renderHook(() => useSearchState());
    act(() => {
      result.current.setQuery("example.com");
    });
    act(() => {
      result.current.submitSearch();
    });
    expect(result.current.submittedQuery).toBe("example.com");
  });

  it("submitWithQuery atomically sets both query and submittedQuery", () => {
    const { result } = renderHook(() => useSearchState());
    act(() => {
      result.current.submitWithQuery("test.com");
    });
    expect(result.current.query).toBe("test.com");
    expect(result.current.submittedQuery).toBe("test.com");
  });

  it("setRecursive updates recursive option", () => {
    const { result } = renderHook(() => useSearchState());
    act(() => {
      result.current.setRecursive(false);
    });
    expect(result.current.options.recursive).toBe(false);
  });

  it("setRecursive(false) clears depth", () => {
    const { result } = renderHook(() => useSearchState());
    act(() => {
      result.current.setDepth(3);
    });
    act(() => {
      result.current.setRecursive(false);
    });
    expect(result.current.options.depth).toBeNull();
  });

  it("setDepth updates depth option", () => {
    const { result } = renderHook(() => useSearchState());
    act(() => {
      result.current.setDepth(2);
    });
    expect(result.current.options.depth).toBe(2);
  });

  it("setSort updates sort option", () => {
    const { result } = renderHook(() => useSearchState());
    act(() => {
      result.current.setSort("not_after_asc");
    });
    expect(result.current.options.sort).toBe("not_after_asc");
  });

  it("setLimit updates limit option", () => {
    const { result } = renderHook(() => useSearchState());
    act(() => {
      result.current.setLimit(100);
    });
    expect(result.current.options.limit).toBe(100);
  });

  it("setIncludeCerts updates include_certs option", () => {
    const { result } = renderHook(() => useSearchState());
    act(() => {
      result.current.setIncludeCerts(true);
    });
    expect(result.current.options.include_certs).toBe(true);
  });

  it("resetOptions restores defaults", () => {
    const { result } = renderHook(() => useSearchState());
    act(() => {
      result.current.setSort("not_after_asc");
      result.current.setLimit(200);
    });
    act(() => {
      result.current.resetOptions();
    });
    expect(result.current.options.sort).toBe("not_before_desc");
    expect(result.current.options.limit).toBe(5);
  });

  it("buildParams assembles params from current state", () => {
    const { result } = renderHook(() => useSearchState());
    act(() => {
      result.current.submitWithQuery("test.io");
    });
    const params = result.current.buildParams("cursor-abc");
    expect(params.q).toBe("test.io");
    expect(params.cursor).toBe("cursor-abc");
  });

  it("buildParams defaults cursor to null", () => {
    const { result } = renderHook(() => useSearchState());
    const params = result.current.buildParams();
    expect(params.cursor).toBeNull();
  });
});
