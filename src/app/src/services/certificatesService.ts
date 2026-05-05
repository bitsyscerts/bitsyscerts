import { apiFetch } from "./apiClient";
import type { CertificateResponse } from "@/types";

export const CERTIFICATE_QUERY_KEYS = {
  detail: (fingerprint: string) =>
    ["certificates", "detail", fingerprint] as const,
} as const;

export async function getCertificate(
  fingerprint: string,
): Promise<CertificateResponse> {
  return apiFetch<CertificateResponse>(
    `/v1/certificates/${encodeURIComponent(fingerprint)}`,
  );
}
