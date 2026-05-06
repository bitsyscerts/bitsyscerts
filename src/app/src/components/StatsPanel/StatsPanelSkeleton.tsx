import { Skeleton, Stack } from "@mantine/core";

/**
 * Skeleton layout matching the shape of StatsSummary + StorageTable for
 * Suspense / loading fallbacks.
 */
export function StatsPanelSkeleton() {
  return (
    <Stack gap="md">
      <Stack gap="md">
        <Skeleton height={72} radius="md" />
        <Skeleton height={72} radius="md" />
        <Skeleton height={72} radius="md" />
        <Skeleton height={220} radius="md" />
      </Stack>
      <Skeleton height={280} radius="md" />
    </Stack>
  );
}
