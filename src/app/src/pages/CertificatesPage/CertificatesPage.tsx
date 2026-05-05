import { Suspense } from "react";
import { Container, Skeleton, Stack } from "@mantine/core";
import { ErrorBoundary } from "@/components/ErrorBoundary/ErrorBoundary";
import { CertificatesContent } from "./CertificatesContent";

function CertsSkeleton() {
  return (
    <Container size="xl" py="md">
      <Stack gap="md">
        <Skeleton height={42} radius="md" />
      </Stack>
    </Container>
  );
}

/**
 * Certificates page: wraps CertificatesContent in ErrorBoundary + Suspense.
 */
export function CertificatesPage() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<CertsSkeleton />}>
        <CertificatesContent />
      </Suspense>
    </ErrorBoundary>
  );
}
