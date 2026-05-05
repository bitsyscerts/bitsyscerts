import { describe, it, expect } from "vitest";
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

  it("throws when used outside of CertStateProvider", () => {
    expect(() => {
      renderHook(() => useCertStateContext());
    }).toThrow("useCertStateContext must be used inside CertStateProvider");
  });
});
