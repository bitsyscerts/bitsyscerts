import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useCertificate } from "@/hooks/useCertificate";

vi.mock("@/services/certificatesService", () => ({
  getCertificate: vi.fn().mockResolvedValue({ fingerprint: "a".repeat(64) }),
  CERTIFICATE_QUERY_KEYS: { detail: (fp: string) => ["certificates", fp] },
}));

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useCertificate", () => {
  it("is disabled when fingerprint is empty", () => {
    const { result } = renderHook(() => useCertificate(""), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("is disabled for non-SHA256 fingerprint", () => {
    const { result } = renderHook(() => useCertificate("not-a-fp"), {
      wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("is enabled for a valid SHA-256 fingerprint", () => {
    const fp = "a".repeat(64);
    const { result } = renderHook(() => useCertificate(fp), { wrapper });
    // enabled=true means fetchStatus will be 'fetching', not 'idle'
    expect(result.current.fetchStatus).not.toBe("idle");
  });
});
