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

  it("throws when used outside of SearchStateProvider", async () => {
    // Suppress console.error and the async jsdom window ErrorEvent that React
    // fires via reportError().  In singleFork mode the event would otherwise
    // be attributed to whichever test happens to be running when the macrotask
    // fires (typically the first test in the next file).
    const consoleSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    const suppressWindowError = (e: ErrorEvent) => {
      e.preventDefault();
      e.stopImmediatePropagation();
    };
    window.addEventListener("error", suppressWindowError, { capture: true });

    expect(() => {
      renderHook(() => useSearchStateContext());
    }).toThrow("useSearchStateContext must be used inside SearchStateProvider");

    // Drain the macrotask queue so the deferred window error fires here.
    await new Promise<void>((resolve) => {
      setTimeout(resolve, 0);
    });

    window.removeEventListener("error", suppressWindowError, { capture: true });
    consoleSpy.mockRestore();
  });
});
