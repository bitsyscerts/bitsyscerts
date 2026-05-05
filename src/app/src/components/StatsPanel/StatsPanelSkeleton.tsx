import { Group, Skeleton, Stack } from "@mantine/core";

/**
 * Skeleton layout matching the shape of StatsSummary + StorageTable for
 * Suspense / loading fallbacks.
 */
export function StatsPanelSkeleton() {
  return (
    <Stack gap="md">
      <Group grow wrap="wrap">
        <Skeleton height={72} radius="md" />
        <Skeleton height={72} radius="md" />
        <Skeleton height={72} radius="md" />
      </Group>
      <Skeleton height={120} radius="md" />
    </Stack>
  );
}
