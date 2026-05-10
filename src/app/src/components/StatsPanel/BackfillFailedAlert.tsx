import { Alert } from "@mantine/core";
import { IconAlertOctagon, IconInfoCircle } from "@tabler/icons-react";

interface BackfillFailedAlertProps {
  failedCount: number;
  /** Whether legacy-ranges dispatch is the active model. */
  isPrimary?: boolean;
}

/**
 * Displays an alert about failed legacy backfill ranges. Shown as a red
 * critical warning only when legacy-ranges dispatch is the active runtime.
 * Under per-log dispatch the same data is shown as a neutral note since old
 * failed-range rows do not reflect current worker health.
 */
export function BackfillFailedAlert({
  failedCount,
  isPrimary = true,
}: BackfillFailedAlertProps) {
  if (!isPrimary) {
    return (
      <Alert
        icon={<IconInfoCircle size={16} />}
        color="gray"
        variant="light"
        title="Legacy failed ranges (informational)"
      >
        {failedCount} legacy range(s) are recorded as <strong>failed</strong>{" "}
        from earlier dispatch runs. Per-log dispatch is now the active runtime;
        these rows do not block current ingestion.
      </Alert>
    );
  }
  return (
    <Alert
      icon={<IconAlertOctagon size={16} />}
      color="red"
      variant="light"
      title="Failed backfill ranges detected"
    >
      {failedCount} range(s) are marked <strong>failed</strong> and will not
      progress until retried or reset. Inspect the logs and run{" "}
      <code>ctpool backfill</code> after resolving the root cause.
    </Alert>
  );
}
