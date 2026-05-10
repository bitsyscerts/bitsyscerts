import { Badge, Group, Stack, Text, ThemeIcon, Title } from "@mantine/core";
import { IconAlertTriangle, IconShieldCheck } from "@tabler/icons-react";

import type { AuditHealth } from "../../types/stats";

interface AuditHealthCardProps {
  auditHealth: AuditHealth;
  /**
   * Whether the active dispatch mode treats audit findings as primary
   * operator signal. In per-log dispatch (default), audit/repair commands
   * are positioned as advanced/debug tools, not routine workflow.
   */
  isPrimary?: boolean;
}

/**
 * Displays a summary card of open audit findings grouped by severity.
 * Renders a green shield when no findings are open, or a warning with
 * per-severity badges when findings are present.
 */
export function AuditHealthCard({
  auditHealth,
  isPrimary = true,
}: AuditHealthCardProps) {
  const isClean = auditHealth.total_open === 0;

  if (isClean) {
    return (
      <Group gap="xs">
        <ThemeIcon color="green" variant="light" size="sm">
          <IconShieldCheck size={14} />
        </ThemeIcon>
        <Text size="sm" c="green">
          No open audit findings.
        </Text>
      </Group>
    );
  }

  return (
    <Stack gap="xs">
      <Group gap="xs">
        <ThemeIcon
          color={isPrimary ? "orange" : "gray"}
          variant="light"
          size="sm"
        >
          <IconAlertTriangle size={14} />
        </ThemeIcon>
        <Title order={6}>{auditHealth.total_open} open audit finding(s)</Title>
      </Group>
      <Group gap="xs">
        {auditHealth.open_critical > 0 && (
          <Badge
            color={isPrimary ? "red" : "gray"}
            variant={isPrimary ? "filled" : "light"}
            size="sm"
          >
            {auditHealth.open_critical} critical
          </Badge>
        )}
        {auditHealth.open_error > 0 && (
          <Badge
            color={isPrimary ? "orange" : "gray"}
            variant={isPrimary ? "filled" : "light"}
            size="sm"
          >
            {auditHealth.open_error} error
          </Badge>
        )}
        {auditHealth.open_warning > 0 && (
          <Badge color="yellow" variant="light" size="sm">
            {auditHealth.open_warning} warning
          </Badge>
        )}
        {auditHealth.open_info > 0 && (
          <Badge color="blue" variant="light" size="sm">
            {auditHealth.open_info} info
          </Badge>
        )}
      </Group>
      <Text size="xs" c="dimmed">
        {isPrimary ? (
          <>
            Run <code>ctpool check-audit-gaps</code> to refresh. Use{" "}
            <code>ctpool fix-audit-findings --dry-run</code> to preview repairs.
          </>
        ) : (
          <>
            Audit findings are advanced/debug diagnostics. Per-log workers
            handle retryable failures inline; audit repair is not routine
            workflow.
          </>
        )}
      </Text>
    </Stack>
  );
}
