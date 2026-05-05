import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDrawerState } from "@/hooks/useDrawerState";
import type { HostnameResult } from "@/types";

const HOSTNAME_ITEM: HostnameResult = {
  id: "host-1",
  hostname: "example.com",
  registrable_domain: "example.com",
  is_wildcard: false,
  first_seen_ct: null,
  last_seen_ct: null,
  latest_cert_not_before: null,
  latest_cert_not_after: null,
  latest_cert: null,
};

describe("useDrawerState", () => {
  it("starts closed with no item", () => {
    const { result } = renderHook(() => useDrawerState());
    expect(result.current.isOpen).toBe(false);
    expect(result.current.item).toBeNull();
  });

  it("opens with a hostname item", () => {
    const { result } = renderHook(() => useDrawerState());
    act(() => {
      result.current.openWith({ type: "hostname", data: HOSTNAME_ITEM });
    });
    expect(result.current.isOpen).toBe(true);
    expect(result.current.item).toMatchObject({ type: "hostname" });
  });

  it("opens with a cert-lookup item", () => {
    const { result } = renderHook(() => useDrawerState());
    act(() => {
      result.current.openWith({ type: "cert-lookup", fingerprint: "abc" });
    });
    expect(result.current.isOpen).toBe(true);
    expect(result.current.item).toMatchObject({
      type: "cert-lookup",
      fingerprint: "abc",
    });
  });

  it("close resets both isOpen and item", () => {
    const { result } = renderHook(() => useDrawerState());
    act(() => {
      result.current.openWith({ type: "cert-lookup", fingerprint: "abc" });
    });
    act(() => {
      result.current.close();
    });
    expect(result.current.isOpen).toBe(false);
    expect(result.current.item).toBeNull();
  });
});
