import {
  Paper,
  SimpleGrid,
  Group,
  Stack,
  Text,
  ThemeIcon,
} from "@mantine/core";
import { IconServer, IconCertificate, IconDatabase } from "@tabler/icons-react";
import { formatNumber } from "@/utils/format";

interface StatsSummaryProps {
  totalHostnames: number;
  totalCertificates: number;
  totalLogs: number;
}

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: number;
}

function StatCard({ icon, label, value }: StatCardProps) {
  return (
    <Paper p="md" radius="md" withBorder>
      <Group gap="sm" wrap="nowrap">
        <ThemeIcon variant="light" size="lg" radius="md">
          {icon}
        </ThemeIcon>
        <Stack gap={2}>
          <Text size="xl" fw={700} lh={1}>
            {formatNumber(value)}
          </Text>
          <Text size="xs" c="dimmed">
            {label}
          </Text>
        </Stack>
      </Group>
    </Paper>
  );
}

/**
 * Renders three stat badge cards for total hostnames, certificates, and logs.
 */
export function StatsSummary({
  totalHostnames,
  totalCertificates,
  totalLogs,
}: StatsSummaryProps) {
  return (
    <SimpleGrid cols={{ base: 3, sm: 1 }} spacing="md">
      <StatCard
        icon={<IconServer size={18} />}
        label="Hostnames"
        value={totalHostnames}
      />
      <StatCard
        icon={<IconCertificate size={18} />}
        label="Certificates"
        value={totalCertificates}
      />
      <StatCard
        icon={<IconDatabase size={18} />}
        label="CT Logs"
        value={totalLogs}
      />
    </SimpleGrid>
  );
}
