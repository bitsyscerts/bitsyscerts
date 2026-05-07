import { Badge, Group } from "@mantine/core";
import { formatLagSeconds, formatPct } from "@/utils/format";

interface LogSyncStatusProps {
  backfillPct: number | null;
  lagSeconds: number | null;
  thresholdSeconds?: number;
}

/**
 * Two-pill sync status indicator for a CT log row.
 *
 * History pill: green "✓ History" when backfill is complete; amber
 *   percentage when still in progress.
 * Live pill: green "● Live" when tail is fresh; amber "⏳ Xm" when stale.
 */
export function LogSyncStatus({
  backfillPct,
  lagSeconds,
  thresholdSeconds = 300,
}: LogSyncStatusProps) {
  const historyDone = backfillPct !== null && backfillPct >= 100;
  const isStale = lagSeconds !== null && lagSeconds >= thresholdSeconds;
  const lagKnown = lagSeconds !== null;

  return (
    <Group gap={4} wrap="nowrap">
      {backfillPct !== null && (
        <Badge
          size="xs"
          variant="light"
          color={historyDone ? "teal" : "orange"}
          title={
            historyDone
              ? "All historical records fetched"
              : `Backfill ${formatPct(backfillPct)} complete`
          }
        >
          {historyDone ? "✓ History" : `▓ ${formatPct(backfillPct)}`}
        </Badge>
      )}
      <Badge
        size="xs"
        variant="light"
        color={!lagKnown ? "gray" : isStale ? "orange" : "teal"}
        title={
          !lagKnown
            ? "No tail cursor yet — worker has not synced this log"
            : isStale
              ? `No new records fetched for ${formatLagSeconds(lagSeconds)}`
              : "Tail cursor is current"
        }
      >
        {!lagKnown
          ? "? Unseen"
          : isStale
            ? `⏳ ${formatLagSeconds(lagSeconds)}`
            : "● Live"}
      </Badge>
    </Group>
  );
}
