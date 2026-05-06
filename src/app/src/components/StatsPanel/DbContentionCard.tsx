import {
  Alert,
  Badge,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Text,
} from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import type { DbContentionStats } from "@/types";
import { formatDateTime, formatNumber } from "@/utils/format";

interface DbContentionCardProps {
  contention: DbContentionStats;
}

interface DetailItemProps {
  label: string;
  value: string;
}

function DetailItem({ label, value }: DetailItemProps) {
  return (
    <Stack gap={2}>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text size="sm" fw={500}>
        {value}
      </Text>
    </Stack>
  );
}

function badgeColor(status: DbContentionStats["status"]): string {
  if (status === "healthy") return "teal";
  if (status === "throttling") return "yellow";
  if (status === "stale") return "red";
  if (status === "disabled") return "gray";
  return "blue";
}

function capLabel(value: number | null): string {
  if (value === null) return "—";
  return formatNumber(value);
}

export function DbContentionCard({ contention }: DbContentionCardProps) {
  return (
    <Paper withBorder radius="md" p="md">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <Stack gap={2}>
            <Text size="sm" fw={600}>
              DB Contention Control
            </Text>
            <Text size="xs" c="dimmed">
              Shared write pressure and pacing
            </Text>
          </Stack>
          <Badge variant="light" color={badgeColor(contention.status)}>
            {contention.status}
          </Badge>
        </Group>

        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
          <DetailItem
            label="Shared pressure"
            value={contention.pressure_ema.toFixed(3)}
          />
          <DetailItem
            label="Base sleep"
            value={`${contention.base_sleep_seconds.toFixed(2)} s`}
          />
          <DetailItem
            label="Shared batch cap"
            value={capLabel(contention.shared_batch_size_cap)}
          />
          <DetailItem
            label="Effective batch cap"
            value={capLabel(contention.effective_batch_size_cap)}
          />
          <DetailItem
            label="Last update"
            value={formatDateTime(contention.updated_at)}
          />
        </SimpleGrid>

        {contention.notes.length > 0 ? (
          <Alert
            icon={
              contention.degraded_mode_active ? (
                <IconAlertTriangle size={16} />
              ) : undefined
            }
            color={contention.degraded_mode_active ? "red" : "gray"}
            variant="light"
          >
            {contention.notes[0]}
          </Alert>
        ) : null}
      </Stack>
    </Paper>
  );
}
