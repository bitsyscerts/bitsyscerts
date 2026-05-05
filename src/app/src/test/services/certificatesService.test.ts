import { describe, it, expect, vi } from "vitest";
import {
  getCertificate,
  CERTIFICATE_QUERY_KEYS,
} from "@/services/certificatesService";

vi.mock("@/services/apiClient", () => ({
  apiFetch: vi.fn().mockResolvedValue({ fingerprint_sha256: "abc" }),
}));

import { apiFetch } from "@/services/apiClient";
const mockApiFetch = vi.mocked(apiFetch);

const FP = "a".repeat(64);

describe("CERTIFICATE_QUERY_KEYS", () => {
  it("returns a stable key array for detail", () => {
    const key = CERTIFICATE_QUERY_KEYS.detail(FP);
    expect(key[0]).toBe("certificates");
    expect(key[1]).toBe("detail");
    expect(key[2]).toBe(FP);
  });
});

describe("getCertificate", () => {
  it("calls apiFetch with the encoded fingerprint path", async () => {
    await getCertificate(FP);
    expect(mockApiFetch).toHaveBeenCalledWith(`/v1/certificates/${FP}`);
  });

  it("URL-encodes the fingerprint", async () => {
    const fp = "ab/cd";
    await getCertificate(fp);
    expect(mockApiFetch).toHaveBeenCalledWith("/v1/certificates/ab%2Fcd");
  });
});
