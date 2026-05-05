import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import {
  SearchStateProvider,
  useSearchStateContext,
} from "@/context/SearchStateContext";

describe("SearchStateContext", () => {
  it("provides search state to consumers", () => {
    const { result } = renderHook(() => useSearchStateContext(), {
      wrapper: SearchStateProvider,
    });
    expect(result.current.query).toBe("");
    expect(result.current.submittedQuery).toBe("");
  });

  it("throws when used outside of SearchStateProvider", () => {
    const consoleSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    expect(() => {
      renderHook(() => useSearchStateContext());
    }).toThrow("useSearchStateContext must be used inside SearchStateProvider");
    consoleSpy.mockRestore();
  });
});
