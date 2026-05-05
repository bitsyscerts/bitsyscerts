import { useQuery } from "@tanstack/react-query";
import {
  getCertificate,
  CERTIFICATE_QUERY_KEYS,
} from "@/services/certificatesService";
import type { CertificateResponse } from "@/types";

const SHA256_RE = /^[0-9a-f]{64}$/i;

/**
 * TanStack Query wrapper for the certificate detail endpoint.
 * Query is disabled when fingerprint is empty or not a valid SHA-256 hex string.
 */
export function useCertificate(fingerprint: string) {
  return useQuery<CertificateResponse>({
    queryKey: CERTIFICATE_QUERY_KEYS.detail(fingerprint),
    queryFn: () => getCertificate(fingerprint),
    enabled: SHA256_RE.test(fingerprint),
  });
}
