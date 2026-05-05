import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  CertStateProvider,
  useCertStateContext,
} from "@/context/CertStateContext";

describe("CertStateContext", () => {
  it("starts with empty input and submittedFp", () => {
    const { result } = renderHook(() => useCertStateContext(), {
      wrapper: CertStateProvider,
    });
    expect(result.current.input).toBe("");
    expect(result.current.submittedFp).toBe("");
  });

  it("setInput updates input without changing submittedFp", () => {
    const { result } = renderHook(() => useCertStateContext(), {
      wrapper: CertStateProvider,
    });
    act(() => {
      result.current.setInput("abc");
    });
    expect(result.current.input).toBe("abc");
    expect(result.current.submittedFp).toBe("");
  });

  it("submitLookup sets both input and submittedFp", () => {
    const { result } = renderHook(() => useCertStateContext(), {
      wrapper: CertStateProvider,
    });
    const fp = "a".repeat(64);
    act(() => {
      result.current.submitLookup(fp);
    });
    expect(result.current.input).toBe(fp);
    expect(result.current.submittedFp).toBe(fp);
  });

  it("throws when used outside of CertStateProvider", async () => {
    const consoleSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    const suppressWindowError = (e: ErrorEvent) => {
      e.preventDefault();
      e.stopImmediatePropagation();
    };
    window.addEventListener("error", suppressWindowError, { capture: true });

    expect(() => {
      renderHook(() => useCertStateContext());
    }).toThrow("useCertStateContext must be used inside CertStateProvider");

    await new Promise<void>((resolve) => {
      setTimeout(resolve, 0);
    });

    window.removeEventListener("error", suppressWindowError, { capture: true });
    consoleSpy.mockRestore();
  });
});
