import { Progress, Stack, Text } from "@mantine/core";
import type { IngestionWorkload } from "@/types";
import { formatCompactNumber, formatRatioPct } from "@/utils/format";

interface BackfillWorkloadSectionProps {
  workload: IngestionWorkload;
}

export function BackfillWorkloadSection({
  workload,
}: BackfillWorkloadSectionProps) {
  const pct =
    workload.sync_percent != null
      ? Math.min(workload.sync_percent * 100, 100)
      : 0;

  return (
    <Stack gap={4}>
      <Text size="sm" fw={600}>
        Backfill workload
      </Text>
      <Progress
        value={pct}
        color="teal"
        radius="sm"
        aria-label={`Backfill progress: ${formatRatioPct(workload.sync_percent)}`}
      />
      <Text size="sm" c="dimmed">
        {formatCompactNumber(workload.planned_observations_completed)} /{" "}
        {formatCompactNumber(workload.planned_observations_total)} observations
        ({formatRatioPct(workload.sync_percent)})
      </Text>
    </Stack>
  );
}
