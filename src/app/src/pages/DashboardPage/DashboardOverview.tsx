/**
 * DashboardOverview — Sprint 8 simplified dashboard.
 *
 * Replaces the old multi-column DashboardContent with three compact summary
 * cards, a system status banner, a collapsible diagnostics accordion, and
 * three detail drawers accessed via "Inspect" buttons.
 */
import { useState } from "react";
import {
  ActionIcon,
  Alert,
  Group,
  SimpleGrid,
  Stack,
  Text,
} from "@mantine/core";
import { IconAlertTriangle, IconRefresh } from "@tabler/icons-react";
import { CTLogsDrawer } from "@/components/StatsPanel/CTLogsDrawer";
import { DiagnosticsSection } from "@/components/StatsPanel/DiagnosticsSection";
import { IndexSummary } from "@/components/StatsPanel/IndexSummary";
import { IndexerActivitySummary } from "@/components/StatsPanel/IndexerActivitySummary";
import { IssuesPanel } from "@/components/StatsPanel/IssuesPanel";
import { StatsPanelSkeleton } from "@/components/StatsPanel/StatsPanelSkeleton";
import { StorageDetailsDrawer } from "@/components/StatsPanel/StorageDetailsDrawer";
import { StorageSummary } from "@/components/StatsPanel/StorageSummary";
import { SystemStatusCard } from "@/components/StatsPanel/SystemStatusCard";
import { WorkerDetailsDrawer } from "@/components/StatsPanel/WorkerDetailsDrawer";
import { useStats } from "@/hooks/useStats";
import { deriveSystemStatus } from "@/utils/deriveSystemStatus";

const AUTO_REFRESH_MS = 10_000;

interface RefreshBarProps {
  updatedAt: number;
  onRefresh: () => void;
}

function RefreshBar({ updatedAt, onRefresh }: RefreshBarProps) {
  const ts = updatedAt > 0 ? new Date(updatedAt).toLocaleTimeString() : null;
  return (
    <Group justify="flex-end" align="center" gap="xs">
      {ts && (
        <Text size="xs" c="dimmed">
          Updated {ts}
        </Text>
      )}
      <ActionIcon
        onClick={onRefresh}
        variant="subtle"
        size="sm"
        aria-label="Refresh statistics"
      >
        <IconRefresh size={14} />
      </ActionIcon>
    </Group>
  );
}

/**
 * Compact dashboard overview with summary cards and detail drawers.
 *
 * This component owns the auto-refresh timer and all drawer open/close state.
 * It composes leaf components only — no local data derivation beyond what is
 * provided by {@link deriveSystemStatus}.
 */
export function DashboardOverview() {
  const { data, isLoading, isError, dataUpdatedAt, refetch } =
    useStats(AUTO_REFRESH_MS);

  const [workersOpen, setWorkersOpen] = useState(false);
  const [logsOpen, setLogsOpen] = useState(false);
  const [storageOpen, setStorageOpen] = useState(false);

  if (isLoading) return <StatsPanelSkeleton />;

  if (isError || !data) {
    return (
      <Alert icon={<IconAlertTriangle size={16} />} color="red" variant="light">
        Could not load statistics.
      </Alert>
    );
  }

  const status = deriveSystemStatus(data);
  const health = data.ingestion_health;
  const quietCount =
    (health?.degraded_logs ?? 0) +
    (health?.retrying_logs ?? 0) +
    (health?.rate_limited_logs ?? 0) +
    (health?.paused_logs ?? 0);
  const quietNote =
    quietCount > 0
      ? `${String(quietCount)} data provider${quietCount === 1 ? "" : "s"} temporarily unavailable — auto-recovering`
      : undefined;

  return (
    <>
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <SystemStatusCard
            level={status.level}
            issueCount={status.issues.length}
            note={quietNote}
          />
          <RefreshBar
            updatedAt={dataUpdatedAt}
            onRefresh={() => void refetch()}
          />
        </Group>

        {status.issues.length > 0 && <IssuesPanel issues={status.issues} />}

        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="sm">
          <IndexSummary
            totalHostnames={data.total_hostnames}
            totalCertificates={data.total_certificates}
            totalLogs={data.total_logs}
            snapshot={data.snapshot}
            onInspectLogs={() => {
              setLogsOpen(true);
            }}
          />
          <IndexerActivitySummary
            workers={data.workers}
            ingestionRate={data.ingestion_rate}
            onInspectWorkers={() => {
              setWorkersOpen(true);
            }}
          />
          <StorageSummary
            storage={data.storage}
            storageProfile={data.storage_profile}
            maintenance={data.maintenance}
            storageProjection={data.storage_projection}
            onStorageDetails={() => {
              setStorageOpen(true);
            }}
          />
        </SimpleGrid>

        <DiagnosticsSection
          backfillRanges={data.backfill_ranges}
          auditHealth={data.audit_health}
          contention={data.db_contention}
        />
      </Stack>

      <WorkerDetailsDrawer
        opened={workersOpen}
        onClose={() => {
          setWorkersOpen(false);
        }}
        workers={data.workers}
      />
      <CTLogsDrawer
        opened={logsOpen}
        onClose={() => {
          setLogsOpen(false);
        }}
        logs={data.logs}
        backfillState={data.backfill_state}
      />
      <StorageDetailsDrawer
        opened={storageOpen}
        onClose={() => {
          setStorageOpen(false);
        }}
        storage={data.storage}
        projection={data.storage_projection}
        maintenance={data.maintenance}
      />
    </>
  );
}
