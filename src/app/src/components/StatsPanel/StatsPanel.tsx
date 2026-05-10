import { Accordion, Alert, Stack, Text } from "@mantine/core";
import { IconChartBar, IconAlertTriangle } from "@tabler/icons-react";
import { useStats } from "@/hooks/useStats";
import { AuditHealthCard } from "./AuditHealthCard";
import { BackfillRangesCard } from "./BackfillRangesCard";
import { BackfillStateCard } from "./BackfillStateCard";
import { StatsSummary } from "./StatsSummary";
import { StorageProfileCard } from "./StorageProfileCard";
import { StorageTable } from "./StorageTable";
import { LogStatsList } from "./LogStatsList";
import { StatsPanelSkeleton } from "./StatsPanelSkeleton";
import { IngestionRateCard } from "./IngestionRateCard";
import { IngestionHealthCard } from "./IngestionHealthCard";
import { LegacyDiagnosticsSection } from "./LegacyDiagnosticsSection";
import { MaintenancePanel } from "./MaintenancePanel";
import { SnapshotFreshnessCard } from "./SnapshotFreshnessCard";
import { TailFreshnessCard } from "./TailFreshnessCard";
import { WorkerActivityCard } from "./WorkerActivityCard";
import { isPerLogPrimaryMode } from "@/utils/statsMode";

/**
 * Collapsible Accordion panel showing ingestion statistics. Uses useStats
 * with a 60s refetch interval; shows skeleton while loading, error alert on
 * failure.
 */
export function StatsPanel() {
  const { data, isLoading, isError } = useStats();

  function renderContent() {
    if (isLoading) return <StatsPanelSkeleton />;
    if (isError || !data) {
      return (
        <Alert
          icon={<IconAlertTriangle size={16} />}
          color="red"
          variant="light"
        >
          Could not load statistics.
        </Alert>
      );
    }
    const perLogPrimary = isPerLogPrimaryMode(data);
    return (
      <Stack gap="lg">
        <SnapshotFreshnessCard snapshot={data.snapshot} />
        <StatsSummary
          totalHostnames={data.total_hostnames}
          totalCertificates={data.total_certificates}
          totalLogs={data.total_logs}
        />
        {data.workers && <WorkerActivityCard workers={data.workers} />}
        {data.ingestion_health && (
          <IngestionHealthCard ingestionHealth={data.ingestion_health} />
        )}
        {data.maintenance && (
          <MaintenancePanel maintenance={data.maintenance} />
        )}
        {data.backfill_state && (
          <BackfillStateCard state={data.backfill_state} />
        )}
        <TailFreshnessCard tailFreshness={data.tail_freshness} />
        <IngestionRateCard ingestionRate={data.ingestion_rate} />
        {!perLogPrimary && (
          <BackfillRangesCard backfillRanges={data.backfill_ranges} isPrimary />
        )}
        {!perLogPrimary && data.audit_health && (
          <AuditHealthCard
            auditHealth={data.audit_health}
            isPrimary={!perLogPrimary}
          />
        )}
        <StorageProfileCard storageProfile={data.storage_profile} />
        <Text size="sm" fw={600}>
          Database Storage
        </Text>
        <StorageTable
          tables={data.storage.tables}
          totalSizeBytes={data.storage.total_size_bytes}
        />
        <Text size="sm" fw={600}>
          CT Logs
        </Text>
        <LogStatsList logs={data.logs} />
        {perLogPrimary && (
          <LegacyDiagnosticsSection
            backfillRanges={data.backfill_ranges}
            auditHealth={data.audit_health}
          />
        )}
      </Stack>
    );
  }

  return (
    <Accordion variant="separated" radius="md">
      <Accordion.Item value="stats">
        <Accordion.Control icon={<IconChartBar size={16} />}>
          <Text size="sm" fw={500}>
            Ingestion Statistics
          </Text>
        </Accordion.Control>
        <Accordion.Panel>{renderContent()}</Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );
}
