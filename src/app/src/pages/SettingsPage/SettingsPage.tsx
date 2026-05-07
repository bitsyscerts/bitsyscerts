import { Suspense, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Paper,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { IconAlertTriangle, IconSettings } from "@tabler/icons-react";
import { ErrorBoundary } from "@/components/ErrorBoundary/ErrorBoundary";
import { StorageSettingsDrawer } from "@/components/StatsPanel/StorageSettingsDrawer";
import { ApiError } from "@/services/apiClient";
import { useStorageSettings } from "@/hooks/useStorageSettings";
import {
  getStorageSettingsHistory,
  SETTINGS_QUERY_KEYS,
} from "@/services/settingsApi";
import type {
  StorageSettingsHistoryItem,
  StorageSettingsResponse,
} from "@/types/settings";
import type { StorageProfileSettings } from "@/types/stats";

const PROFILE_COLORS: Record<string, string> = {
  lite: "teal",
  standard: "blue",
  research: "violet",
  archive: "red",
  custom: "orange",
};

interface ActiveProfileCardProps {
  settings: StorageSettingsResponse;
  onEdit: () => void;
}

function ActiveProfileCard({ settings, onEdit }: ActiveProfileCardProps) {
  const updatedDate = new Date(settings.updated_at).toLocaleString();
  return (
    <Paper withBorder radius="md" p="md">
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start">
          <Stack gap={4}>
            <Text size="sm" fw={600}>
              Storage Profile
            </Text>
            <Badge
              color={PROFILE_COLORS[settings.storage_profile] ?? "gray"}
              variant="light"
            >
              {settings.storage_profile}
            </Badge>
          </Stack>
          <Button
            leftSection={<IconSettings size={14} />}
            variant="light"
            size="xs"
            onClick={onEdit}
          >
            Edit
          </Button>
        </Group>
        <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="xs">
          <SettingRow label="Cert mode" value={settings.cert_storage_mode} />
          <SettingRow
            label="Hostname retention"
            value={settings.hostname_retention_mode}
          />
          <SettingRow
            label="Backfill days"
            value={String(settings.backfill_days)}
          />
          <SettingRow
            label="Cert retention"
            value={`${String(settings.cert_retention_days)} d`}
          />
          <SettingRow
            label="Observation retention"
            value={`${String(settings.observation_retention_days)} d`}
          />
          <SettingRow
            label="Metrics retention"
            value={`${String(settings.metrics_retention_days)} d`}
          />
        </SimpleGrid>
        <Text size="xs" c="dimmed">
          Last updated {updatedDate}
          {settings.updated_by ? ` by ${settings.updated_by}` : ""}
        </Text>
      </Stack>
    </Paper>
  );
}

function SettingRow({ label, value }: { label: string; value: string }) {
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

function ProfileHistorySection() {
  const { data, isLoading } = useQuery<StorageSettingsHistoryItem[]>({
    queryKey: SETTINGS_QUERY_KEYS.storageSettingsHistory,
    queryFn: getStorageSettingsHistory,
    staleTime: 60_000,
  });

  if (isLoading) return <Skeleton height={80} />;
  if (!data?.length) return null;

  return (
    <Paper withBorder radius="md" p="md">
      <Stack gap="sm">
        <Text size="sm" fw={600}>
          Profile History
        </Text>
        {data.map((item) => (
          <Group key={item.settings_hash} justify="space-between" wrap="nowrap">
            <Badge
              color={PROFILE_COLORS[item.storage_profile] ?? "gray"}
              variant="outline"
              size="sm"
            >
              {item.storage_profile}
            </Badge>
            <Text size="xs" c="dimmed">
              {new Date(item.last_seen_at).toLocaleDateString()}
            </Text>
          </Group>
        ))}
      </Stack>
    </Paper>
  );
}

function NotBootstrappedCard({ onConfigure }: { onConfigure: () => void }) {
  return (
    <Paper withBorder radius="md" p="md">
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start">
          <Text size="sm" fw={600}>
            Storage Profile
          </Text>
          <Button
            leftSection={<IconSettings size={14} />}
            variant="light"
            size="xs"
            onClick={onConfigure}
          >
            Configure
          </Button>
        </Group>
        <Text size="sm" c="dimmed">
          Storage settings have not been initialised yet. Start the ctpool
          worker to bootstrap automatically, or configure manually.
        </Text>
      </Stack>
    </Paper>
  );
}

function SettingsContent() {
  const { data, isLoading, isError, error } = useStorageSettings();
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (isLoading) return <Skeleton height={200} />;

  const isNotBootstrapped =
    isError && error instanceof ApiError && error.status === 404;

  if (isNotBootstrapped) {
    return (
      <Stack gap="md">
        <Title order={3} fw={600}>
          Settings
        </Title>
        <NotBootstrappedCard
          onConfigure={() => {
            setDrawerOpen(true);
          }}
        />
        <StorageSettingsDrawer
          opened={drawerOpen}
          onClose={() => {
            setDrawerOpen(false);
          }}
          currentSettings={null}
        />
      </Stack>
    );
  }

  if (isError || !data) {
    return (
      <Alert icon={<IconAlertTriangle size={16} />} color="red" variant="light">
        Could not load storage settings.
      </Alert>
    );
  }

  // StorageSettingsResponse is structurally compatible with StorageProfileSettings
  // for the drawer's display purposes (same retention fields).
  const drawerSettings = data as unknown as StorageProfileSettings;

  return (
    <Stack gap="md">
      <Title order={3} fw={600}>
        Settings
      </Title>
      <ActiveProfileCard
        settings={data}
        onEdit={() => {
          setDrawerOpen(true);
        }}
      />
      <ProfileHistorySection />
      <StorageSettingsDrawer
        opened={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
        }}
        currentSettings={drawerSettings}
      />
    </Stack>
  );
}

/** Runtime configuration page at /settings. */
export function SettingsPage() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<Skeleton height={200} />}>
        <Container size="md" py="md">
          <SettingsContent />
        </Container>
      </Suspense>
    </ErrorBoundary>
  );
}
