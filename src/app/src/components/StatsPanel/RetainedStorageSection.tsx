import { Stack, Text } from "@mantine/core";
import type { StorageProjection } from "@/types";
import { formatRatioPct, formatStorageSize } from "@/utils/format";
import { computeStorageCeiling } from "@/utils/projectionUtils";

interface RetainedStorageSectionProps {
  projection: StorageProjection;
}

export function RetainedStorageSection({
  projection,
}: RetainedStorageSectionProps) {
  const { ceilingBytes, pct } = computeStorageCeiling(projection);

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
