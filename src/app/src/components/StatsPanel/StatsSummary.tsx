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
    <Paper p="sm" radius="md" withBorder>
      <Group justify="space-between" align="center" gap="sm" wrap="nowrap">
        <Stack gap={1}>
          <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
            {label}
          </Text>
          <Text size="lg" fw={700} lh={1.1}>
            {formatNumber(value)}
          </Text>
        </Stack>
        <ThemeIcon variant="light" size="md" radius="xl">
          {icon}
        </ThemeIcon>
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
    <SimpleGrid cols={{ base: 1, xs: 3 }} spacing="sm">
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
