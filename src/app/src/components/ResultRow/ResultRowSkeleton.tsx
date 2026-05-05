import { Group, Skeleton, Stack } from "@mantine/core";

/**
 * Skeleton placeholder shaped like a HostnameResultRow for Suspense fallbacks
 * and loading states.
 */
export function ResultRowSkeleton() {
  return (
    <Stack gap={6} p="sm">
      <Group justify="space-between">
        <Skeleton height={16} width="40%" radius="sm" />
        <Skeleton height={18} width={60} radius="xl" />
      </Group>
      <Skeleton height={12} width="25%" radius="sm" />
      <Group gap="xs">
        <Skeleton height={12} width={120} radius="sm" />
        <Skeleton height={12} width={120} radius="sm" />
      </Group>
    </Stack>
  );
}
