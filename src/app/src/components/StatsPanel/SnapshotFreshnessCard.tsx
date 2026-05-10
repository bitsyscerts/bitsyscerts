import { Badge, Group, Paper, Text } from "@mantine/core";
import {
  IconClock,
  IconAlertCircle,
  IconCircleCheck,
} from "@tabler/icons-react";
import type { SnapshotMetadata } from "@/types/stats";
import { formatLagSeconds } from "@/utils/format";

interface SnapshotFreshnessCardProps {
  snapshot: SnapshotMetadata | null | undefined;
}

/**
 * Sprint 5: small, always-visible "Updated Xs ago" badge so the operator
 * never reads stale numbers as current.  Renders three distinct states:
 *
 *   - fresh snapshot or live  -> green check + age in seconds/minutes.
 *   - stale (age > threshold) -> orange alert + explicit "Stats stale" copy.
 *   - no snapshot generated   -> dimmed neutral notice.
 *
 * Stays quiet when healthy; raises voice only when the operator should
 * act.
 */
export function SnapshotFreshnessCard({
  snapshot,
}: SnapshotFreshnessCardProps) {
  if (
    !snapshot ||
    (snapshot.age_seconds === null && snapshot.source === "none")
  ) {
    return (
      <Paper
        withBorder
        radius="md"
        p="xs"
        data-testid="snapshot-freshness-none"
      >
        <Group gap="xs">
          <IconClock size={14} />
          <Text size="xs" c="dimmed">
            Stats snapshot has not been generated yet.
          </Text>
        </Group>
      </Paper>
    );
  }

  const ageSeconds = snapshot.age_seconds;
  const relative =
    ageSeconds === null
      ? "unknown"
      : formatLagSeconds(Math.max(0, Math.floor(ageSeconds)));

  if (snapshot.is_stale) {
    return (
      <Paper
        withBorder
        radius="md"
        p="xs"
        bg="var(--mantine-color-orange-light)"
        data-testid="snapshot-freshness-stale"
      >
        <Group gap="xs">
          <IconAlertCircle size={14} color="var(--mantine-color-orange-7)" />
          <Text size="xs" fw={500}>
            Stats stale &mdash; last updated {relative} ago
          </Text>
          {snapshot.stale_threshold_seconds !== null && (
            <Badge size="xs" variant="light" color="orange">
              threshold {snapshot.stale_threshold_seconds}s
            </Badge>
          )}
        </Group>
      </Paper>
    );
  }

  return (
    <Paper withBorder radius="md" p="xs" data-testid="snapshot-freshness-fresh">
      <Group gap="xs">
        <IconCircleCheck size={14} color="var(--mantine-color-green-7)" />
        <Text size="xs" c="dimmed">
          Updated {relative} ago
        </Text>
        <Badge size="xs" variant="light" color="gray">
          source: {snapshot.source}
        </Badge>
      </Group>
    </Paper>
  );
}
