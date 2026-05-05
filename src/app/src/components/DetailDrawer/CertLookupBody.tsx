import { useEffect } from "react";
import { Alert, Skeleton, Stack } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useCertificate } from "@/hooks/useCertificate";
import { CertDetailBody } from "./CertDetailBody";

interface CertLookupBodyProps {
  fingerprint: string;
  /** Called once with the subject CN (or DN fallback) after data loads. */
  onCnResolved?: (cn: string) => void;
}

/**
 * Fetches the full CertificateResponse for the given SHA-256 fingerprint and
 * renders CertDetailBody — the same component used on the Certificates page,
 * guaranteeing a consistent first-class certificate view everywhere.
 */
export function CertLookupBody({
  fingerprint,
  onCnResolved,
}: CertLookupBodyProps) {
  const { data, isLoading, isError, error } = useCertificate(fingerprint);

  useEffect(() => {
    if (!data || !onCnResolved) return;
    onCnResolved(data.subject_common_name ?? data.subject_dn);
  }, [data, onCnResolved]);
  if (isLoading) {
    return (
      <Stack gap="sm" p="md">
        {Array.from({ length: 8 }).map((_, i) => (
          // biome-ignore lint: static skeleton list
          <Skeleton key={i} height={28} radius="sm" />
        ))}
      </Stack>
    );
  }

  if (isError || !data) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} color="red" m="md">
        {error instanceof Error ? error.message : "Could not load certificate."}
      </Alert>
    );
  }

  return <CertDetailBody cert={data} />;
}
