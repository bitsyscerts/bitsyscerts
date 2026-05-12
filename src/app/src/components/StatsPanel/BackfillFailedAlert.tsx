import { Alert } from "@mantine/core";
import { IconAlertOctagon } from "@tabler/icons-react";

interface BackfillFailedAlertProps {
  failedCount: number;
}

export function BackfillFailedAlert({ failedCount }: BackfillFailedAlertProps) {
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
