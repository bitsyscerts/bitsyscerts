import { Suspense } from "react";
import { Container, Skeleton, Stack } from "@mantine/core";
import { ErrorBoundary } from "@/components/ErrorBoundary/ErrorBoundary";
import { HostsContent } from "./SearchPageContent";

function HostsSkeleton() {
  return (
    <Container size="xl" py="md">
      <Stack gap="md">
        <Skeleton height={42} radius="md" />
        <Stack gap="sm">
          {Array.from({ length: 5 }).map((_, i) => (
            // biome-ignore lint: static skeleton list
            <Skeleton key={i} height={72} radius="md" />
          ))}
        </Stack>
      </Stack>
    </Container>
  );
}

/**
 * Hosts page: wraps HostsContent in an ErrorBoundary and Suspense with a
 * skeleton fallback.
 */
export function HostsPage() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<HostsSkeleton />}>
        <HostsContent />
      </Suspense>
    </ErrorBoundary>
  );
}
