import { Alert, Badge, Group, Stack, Text } from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import type { BackfillRangeStats } from "@/types/stats";
import { BackfillFailedAlert } from "./BackfillFailedAlert";

interface BackfillRangesCardProps {
  backfillRanges: BackfillRangeStats;
}

export function BackfillRangesCard({
  backfillRanges,
}: BackfillRangesCardProps) {
  const isStale = backfillRanges.stale_in_progress > 0;

  return (
    <Stack gap="xs">
      <Text size="sm" fw={600}>
        Backfill Range Status
      </Text>
      {isStale && (
        <Alert
          icon={<IconAlertTriangle size={16} />}
          color="yellow"
          variant="light"
          title="Stale backfill claims detected"
        >
          {backfillRanges.stale_in_progress} range(s) are stuck in{" "}
          <strong>in_progress</strong> with no recent heartbeat. A worker may
          have crashed. Run <code>ctpool reap-stale-backfill-claims</code> to
          release them.
        </Alert>
      )}
      {backfillRanges.failed > 0 && (
        <BackfillFailedAlert failedCount={backfillRanges.failed} />
      )}
      <Group gap="sm" wrap="wrap">
        <Badge color="gray" variant="light">
          Pending: {backfillRanges.pending.toLocaleString()}
        </Badge>
        <Badge color="blue" variant="light">
          In Progress: {backfillRanges.in_progress.toLocaleString()}
        </Badge>
        {isStale && (
          <Badge color="yellow" variant="filled">
            Stale: {backfillRanges.stale_in_progress.toLocaleString()}
          </Badge>
        )}
        <Badge color="green" variant="light">
          Completed: {backfillRanges.completed.toLocaleString()}
        </Badge>
        {backfillRanges.failed > 0 && (
          <Badge color="red" variant="light">
            Failed: {backfillRanges.failed.toLocaleString()}
          </Badge>
        )}
      </Group>
    </Stack>
  );
}
