import { useState } from "react";
import { Drawer, ScrollArea, Stack, Text } from "@mantine/core";
import { useUpdateStorageSettings } from "@/hooks/useUpdateStorageSettings";
import type { StorageProfileSettings } from "@/types/stats";
import type { UpdateStorageSettingsRequest } from "@/types/settings";
import { StorageSettingsForm } from "./StorageSettingsForm";

interface StorageSettingsDrawerProps {
  opened: boolean;
  onClose: () => void;
  currentSettings?: StorageProfileSettings | null;
}

export function StorageSettingsDrawer({
  opened,
  onClose,
  currentSettings,
}: StorageSettingsDrawerProps) {
  const mutation = useUpdateStorageSettings();
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function handleSubmit(values: UpdateStorageSettingsRequest) {
    setSubmitError(null);
    try {
      await mutation.mutateAsync(values);
      onClose();
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "An unexpected error occurred. Please try again.";
      setSubmitError(msg);
    }
  }

  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      title={
        <Stack gap={2}>
          <Text fw={600}>Storage Settings</Text>
          <Text size="xs" c="dimmed">
            Changes are prospective only — existing data is not auto-pruned.
          </Text>
        </Stack>
      }
      position="right"
      size="md"
      scrollAreaComponent={ScrollArea.Autosize}
    >
      <StorageSettingsForm
        currentSettings={currentSettings}
        onSuccess={onClose}
        onSubmit={handleSubmit}
        isSubmitting={mutation.isPending}
        submitError={submitError}
      />
    </Drawer>
  );
}
