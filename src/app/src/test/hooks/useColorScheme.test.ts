import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { ColorSchemeProvider } from "@/context/ColorSchemeContext";
import { useColorScheme } from "@/hooks/useColorScheme";

describe("useColorScheme", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("starts with system scheme by default", () => {
    const { result } = renderHook(() => useColorScheme(), {
      wrapper: ColorSchemeProvider,
    });
    expect(result.current.colorScheme).toBe("system");
  });

  it("cycles system → light → dark → system", () => {
    const { result } = renderHook(() => useColorScheme(), {
      wrapper: ColorSchemeProvider,
    });

    act(() => {
      result.current.cycleScheme();
    });
    expect(result.current.colorScheme).toBe("light");

    act(() => {
      result.current.cycleScheme();
    });
    expect(result.current.colorScheme).toBe("dark");

    act(() => {
      result.current.cycleScheme();
    });
    expect(result.current.colorScheme).toBe("system");
  });

  it("reads the stored scheme from localStorage", () => {
    localStorage.setItem("bitsyscerts-color-scheme", "dark");
    const { result } = renderHook(() => useColorScheme(), {
      wrapper: ColorSchemeProvider,
    });
    expect(result.current.colorScheme).toBe("dark");
  });
});
