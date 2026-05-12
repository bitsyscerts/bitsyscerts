import {
  Alert,
  Badge,
  Card,
  Group,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from "@mantine/core";
import {
  IconAlertTriangle,
  IconClockHour4,
  IconRecycle,
  IconShieldCheck,
} from "@tabler/icons-react";

import type { MaintenanceStatus } from "../../types/stats";

interface MaintenancePanelProps {
  maintenance: MaintenanceStatus;
}

/**
 * Retention-maintenance summary card.
 *
 * Surfaces whether the active storage profile (Lite / Standard / Research /
 * Archive) is being enforced by the periodic ``prune-for-storage-profile``
 * job, when it last ran, what it deleted, and when it is next due.
 */
export function MaintenancePanel({ maintenance }: MaintenancePanelProps) {
  const isFailed = maintenance.last_prune_status === "failed";
  const neverRan = maintenance.status === "never_ran";

  return (
    <Card withBorder padding="md" radius="md">
      <Stack gap="sm">
        <Header maintenance={maintenance} />
        {neverRan && <NeverRanAlert profile={maintenance.active_profile} />}
        {isFailed && <FailedAlert errorMessage={maintenance.error_message} />}
        {!neverRan && !isFailed && <DeletedGrid maintenance={maintenance} />}
        {maintenance.next_prune_due_at && (
          <Group gap="xs" align="center">
            <IconClockHour4 size={14} />
            <Text size="xs" c="dimmed">
              Next scheduled maintenance:{" "}
              {formatLocalTime(maintenance.next_prune_due_at)}
            </Text>
          </Group>
        )}
      </Stack>
    </Card>
  );
}

function Header({ maintenance }: { maintenance: MaintenanceStatus }) {
  const enforcementColor = maintenance.is_enforced
    ? "green"
    : maintenance.last_prune_status === "failed"
      ? "red"
      : "yellow";
  const enforcementLabel = maintenance.is_enforced
    ? `${maintenance.active_profile ?? "active"} profile is being enforced`
    : maintenance.last_prune_status === "failed"
      ? "retention maintenance failed"
      : "retention maintenance not yet enforced";
  return (
    <Group justify="space-between" align="center">
      <Group gap="xs" align="center">
        <ThemeIcon color={enforcementColor} variant="light" size="md">
          {maintenance.is_enforced ? (
            <IconShieldCheck size={16} />
          ) : (
            <IconRecycle size={16} />
          )}
        </ThemeIcon>
        <Title order={5}>Retention Maintenance</Title>
      </Group>
      <Badge color={enforcementColor} variant="light">
        {enforcementLabel}
      </Badge>
    </Group>
  );
}

function NeverRanAlert({ profile }: { profile: string | null }) {
  return (
    <Alert
      icon={<IconAlertTriangle size={14} />}
      color="yellow"
      variant="light"
    >
      Retention maintenance has not run yet.{" "}
      {profile ? `${profile} mode` : "The active profile"} may temporarily
      retain more data until maintenance completes.
    </Alert>
  );
}

function FailedAlert({ errorMessage }: { errorMessage: string | null }) {
  return (
    <Alert icon={<IconAlertTriangle size={14} />} color="red" variant="light">
      Retention maintenance failed. The active profile may grow beyond its
      expected footprint.
      {errorMessage && (
        <Text size="xs" mt={4} c="dimmed">
          {errorMessage}
        </Text>
      )}
    </Alert>
  );
}

function DeletedGrid({ maintenance }: { maintenance: MaintenanceStatus }) {
  const deleted = maintenance.last_prune_deleted;
  return (
    <>
      <Text size="xs" c="dimmed">
        Last prune: {maintenance.last_prune_status ?? "unknown"} (
        {formatRelativeAge(maintenance.last_prune_completed_at)}).
      </Text>
      <SimpleGrid cols={{ base: 2, sm: 5 }} spacing="xs">
        <DeletedStat label="Certificates" value={deleted.certificates} />
        <DeletedStat
          label="Cert ↔ Hostname"
          value={deleted.certificate_hostnames}
        />
        <DeletedStat label="Observations" value={deleted.observations} />
        <DeletedStat label="Outcomes" value={deleted.entry_outcomes} />
        <DeletedStat label="Metrics" value={deleted.ingestion_metrics} />
      </SimpleGrid>
    </>
  );
}

function DeletedStat({ label, value }: { label: string; value: number }) {
  return (
    <Stack gap={2}>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={600}>{formatNumber(value)}</Text>
    </Stack>
  );
}

function formatNumber(value: number): string {
  return value.toLocaleString("en-US");
}

function formatRelativeAge(isoString: string | null): string {
  if (!isoString) return "no recent run";
  const ts = Date.parse(isoString);
  if (Number.isNaN(ts)) return "unknown";
  const ageSec = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (ageSec < 60) return `${String(ageSec)}s ago`;
  if (ageSec < 3600) return `${String(Math.floor(ageSec / 60))} minutes ago`;
  if (ageSec < 86400) return `${String(Math.floor(ageSec / 3600))} hours ago`;
  return `${String(Math.floor(ageSec / 86400))} days ago`;
}

function formatLocalTime(isoString: string): string {
  const ts = Date.parse(isoString);
  if (Number.isNaN(ts)) return isoString;
  return new Date(ts).toLocaleString();
}
