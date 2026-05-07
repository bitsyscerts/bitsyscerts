import { Stack, Text } from "@mantine/core";
import type { StorageProjection } from "@/types";
import { formatRatioPct, formatStorageSize } from "@/utils/format";

interface RetainedStorageSectionProps {
  projection: StorageProjection;
}

export function RetainedStorageSection({
  projection,
}: RetainedStorageSectionProps) {
  const profile = projection.profile ?? null;
  const projectedLabel =
    profile != null && profile !== "archive"
      ? `~${formatStorageSize(projection.projected_final_database_size_bytes)} retained`
      : `~${formatStorageSize(projection.projected_final_database_size_bytes)} projected`;

  return (
    <Stack gap={4} maw={280}>
      <Text size="sm" fw={600}>
        {formatStorageSize(projection.database_size_bytes)} used of{" "}
        {projectedLabel}
      </Text>
      <Text size="sm" c="dimmed">
        {formatRatioPct(projection.storage_percent_of_projected)} of projected
        storage
      </Text>
    </Stack>
  );
}
