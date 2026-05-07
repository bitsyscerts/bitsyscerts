import { useState } from "react";
import {
  Badge,
  Button,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Text,
} from "@mantine/core";
import { IconSettings } from "@tabler/icons-react";
import type { StorageProfileSettings } from "@/types/stats";
import { StorageSettingsDrawer } from "./StorageSettingsDrawer";

interface StorageProfileCardProps {
  storageProfile: StorageProfileSettings | null | undefined;
}

const PROFILE_COLORS: Record<string, string> = {
  lite: "teal",
  standard: "blue",
  research: "violet",
  archive: "red",
  custom: "orange",
};

function ProfileBadge({ profile }: { profile: string }) {
  return (
    <Badge color={PROFILE_COLORS[profile] ?? "gray"} variant="light">
      {profile}
    </Badge>
  );
}

function SettingItem({ label, value }: { label: string; value: string }) {
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

export function StorageProfileCard({
  storageProfile,
}: StorageProfileCardProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (!storageProfile) {
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
              onClick={() => {
                setDrawerOpen(true);
              }}
            >
              Configure
            </Button>
          </Group>
          <Text size="sm" c="dimmed">
            No profile configured yet. Settings will be seeded on next worker
            startup using bootstrap defaults.
          </Text>
        </Stack>
        <StorageSettingsDrawer
          opened={drawerOpen}
          onClose={() => {
            setDrawerOpen(false);
          }}
        />
      </Paper>
    );
  }

  return (
    <Paper withBorder radius="md" p="md">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <Stack gap={2}>
            <Text size="sm" fw={600}>
              Storage Profile
            </Text>
            <Text size="xs" c="dimmed">
              Active database-backed configuration
            </Text>
          </Stack>
          <Group gap="xs">
            <ProfileBadge profile={storageProfile.storage_profile} />
            <Button
              leftSection={<IconSettings size={14} />}
              variant="light"
              size="xs"
              onClick={() => {
                setDrawerOpen(true);
              }}
            >
              Configure
            </Button>
          </Group>
        </Group>

        <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="sm">
          <SettingItem
            label="Cert storage"
            value={storageProfile.cert_storage_mode}
          />
          <SettingItem
            label="Hostname retention"
            value={storageProfile.hostname_retention_mode}
          />
          <SettingItem
            label="Backfill days"
            value={String(storageProfile.backfill_days)}
          />
          <SettingItem
            label="Cert retention"
            value={`${String(storageProfile.cert_retention_days)}d`}
          />
          <SettingItem
            label="Obs retention"
            value={`${String(storageProfile.observation_retention_days)}d`}
          />
          <SettingItem
            label="Metrics retention"
            value={`${String(storageProfile.metrics_retention_days)}d`}
          />
        </SimpleGrid>

        {storageProfile.settings_hash ? (
          <Text size="xs" c="dimmed" ff="monospace">
            hash: {storageProfile.settings_hash.slice(0, 16)}…
          </Text>
        ) : null}
      </Stack>

      <StorageSettingsDrawer
        opened={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
        }}
        currentSettings={storageProfile}
      />
    </Paper>
  );
}
