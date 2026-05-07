import { Badge } from "@mantine/core";
import { formatLagSeconds } from "@/utils/format";

interface LogStaleBadgeProps {
  lagSeconds: number | null;
  thresholdSeconds?: number;
}

/**
 * Renders a fresh/stale Badge for a single CT log row based on tail cursor lag.
 * Returns null when lag is not available.
 */
export function LogStaleBadge({
  lagSeconds,
  thresholdSeconds = 300,
}: LogStaleBadgeProps) {
  if (lagSeconds === null) return null;
  const isStale = lagSeconds >= thresholdSeconds;
  return (
    <Badge
      size="xs"
      variant="light"
      color={isStale ? "red" : "teal"}
      title={`Tail lag: ${formatLagSeconds(lagSeconds)}`}
    >
      {isStale ? `stale ${formatLagSeconds(lagSeconds)}` : "fresh"}
    </Badge>
  );
}
