import { Stack, Text } from "@mantine/core";
import type { StorageProjection } from "@/types";
import { formatRatioPct, formatStorageSize } from "@/utils/format";

interface RetainedStorageSectionProps {
  projection: StorageProjection;
}

export function RetainedStorageSection({
  projection,
}: RetainedStorageSectionProps) {
  const ceilingBytes =
    projection.projection_high_bytes ??
    projection.projected_final_database_size_bytes;
  const pct =
    ceilingBytes != null && ceilingBytes > 0
      ? projection.database_size_bytes / ceilingBytes
      : (projection.storage_percent_of_projected ?? null);

  return (
    <Stack gap={4} maw={280}>
      <Text size="sm" fw={600}>
        {formatStorageSize(projection.database_size_bytes)} of ~
        {formatStorageSize(ceilingBytes)} projected max
      </Text>
      <Text size="sm" c="dimmed">
        {formatRatioPct(pct)} of projected storage
      </Text>
    </Stack>
  );
}
