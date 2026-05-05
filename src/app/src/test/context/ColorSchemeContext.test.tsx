import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  ColorSchemeProvider,
  useColorSchemeContext,
} from "@/context/ColorSchemeContext";

describe("ColorSchemeContext", () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    localStorage.clear();
  });

  it("provides default system scheme", () => {
    const { result } = renderHook(() => useColorSchemeContext(), {
      wrapper: ColorSchemeProvider,
    });
    expect(result.current.colorScheme).toBe("system");
  });

  it("setColorScheme persists to localStorage", () => {
    const { result } = renderHook(() => useColorSchemeContext(), {
      wrapper: ColorSchemeProvider,
    });
    act(() => {
      result.current.setColorScheme("dark");
    });
    expect(result.current.colorScheme).toBe("dark");
    expect(localStorage.getItem("bitsyscerts-color-scheme")).toBe("dark");
  });

  it("reads stored value on mount", () => {
    localStorage.setItem("bitsyscerts-color-scheme", "light");
    const { result } = renderHook(() => useColorSchemeContext(), {
      wrapper: ColorSchemeProvider,
    });
    expect(result.current.colorScheme).toBe("light");
  });

  it("ignores invalid stored values and defaults to system", () => {
    localStorage.setItem("bitsyscerts-color-scheme", "invalid-value");
    const { result } = renderHook(() => useColorSchemeContext(), {
      wrapper: ColorSchemeProvider,
    });
    expect(result.current.colorScheme).toBe("system");
  });

  it("throws when used outside of ColorSchemeProvider", async () => {
    const consoleSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    const suppressWindowError = (e: ErrorEvent) => {
      e.preventDefault();
      e.stopImmediatePropagation();
    };
    window.addEventListener("error", suppressWindowError, { capture: true });

    expect(() => {
      renderHook(() => useColorSchemeContext());
    }).toThrow();

    await new Promise<void>((resolve) => {
      setTimeout(resolve, 0);
    });

    window.removeEventListener("error", suppressWindowError, { capture: true });
    consoleSpy.mockRestore();
  });
});
