import { Accordion, Alert, Stack, Text } from "@mantine/core";
import { IconChartBar, IconAlertTriangle } from "@tabler/icons-react";
import { useStats } from "@/hooks/useStats";
import { StatsSummary } from "./StatsSummary";
import { StorageTable } from "./StorageTable";
import { LogStatsList } from "./LogStatsList";
import { StatsPanelSkeleton } from "./StatsPanelSkeleton";

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
    return (
      <Stack gap="lg">
        <StatsSummary
          totalHostnames={data.total_hostnames}
          totalCertificates={data.total_certificates}
          totalLogs={data.total_logs}
        />
        <Text size="sm" fw={600}>
          Database Storage
        </Text>
        <StorageTable
          tables={data.storage.tables}
          totalPretty={data.storage.total_size_pretty}
        />
        <Text size="sm" fw={600}>
          CT Logs
        </Text>
        <LogStatsList logs={data.logs} />
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
