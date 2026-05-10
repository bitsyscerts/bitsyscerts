import { Alert, Badge, Group, Stack, Text } from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import type { BackfillRangeStats } from "@/types/stats";
import { BackfillFailedAlert } from "./BackfillFailedAlert";

interface BackfillRangesCardProps {
  backfillRanges: BackfillRangeStats;
  /**
   * When true, this card represents the primary backfill source of truth
   * (legacy-ranges dispatch mode active). When false, it is shown only as
   * advanced/debug information and warnings are demoted to neutral copy.
   */
  isPrimary?: boolean;
}

/**
 * Displays backfill range status counts. Renders as primary (red/yellow
 * alerts) only when the active dispatch mode is legacy-ranges. In per-log
 * mode the same data is rendered as advanced/debug history.
 */
export function BackfillRangesCard({
  backfillRanges,
  isPrimary = true,
}: BackfillRangesCardProps) {
  const isStale = backfillRanges.stale_in_progress > 0;

  return (
    <Stack gap="xs">
      <Text size="sm" fw={600}>
        {isPrimary ? "Backfill Range Status" : "Legacy Backfill Range Status"}
      </Text>
      {!isPrimary && (
        <Text size="xs" c="dimmed">
          Legacy range counters from earlier ingestion runs. Per-log dispatch is
          the active runtime; these numbers do not reflect current worker
          health.
        </Text>
      )}
      {isStale && isPrimary && (
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
        <BackfillFailedAlert
          failedCount={backfillRanges.failed}
          isPrimary={isPrimary}
        />
      )}
      <Group gap="sm" wrap="wrap">
        <Badge color="gray" variant="light">
          Pending: {backfillRanges.pending.toLocaleString()}
        </Badge>
        <Badge color="blue" variant="light">
          In Progress: {backfillRanges.in_progress.toLocaleString()}
        </Badge>
        {isStale && (
          <Badge
            color={isPrimary ? "yellow" : "gray"}
            variant={isPrimary ? "filled" : "light"}
          >
            Stale: {backfillRanges.stale_in_progress.toLocaleString()}
          </Badge>
        )}
        <Badge color="green" variant="light">
          Completed: {backfillRanges.completed.toLocaleString()}
        </Badge>
        {backfillRanges.failed > 0 && (
          <Badge color={isPrimary ? "red" : "gray"} variant="light">
            Failed: {backfillRanges.failed.toLocaleString()}
          </Badge>
        )}
      </Group>
    </Stack>
  );
}
