import { SimpleGrid, Skeleton, Stack } from "@mantine/core";

/**
 * Skeleton layout matching the shape of StatsSummary + StorageTable for
 * Suspense / loading fallbacks.
 */
export function StatsPanelSkeleton() {
  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 1, xs: 3 }} spacing="sm">
        <Skeleton height={64} radius="md" />
        <Skeleton height={64} radius="md" />
        <Skeleton height={64} radius="md" />
      </SimpleGrid>
      <Skeleton height={220} radius="md" />
      <Skeleton height={280} radius="md" />
    </Stack>
  );
}
