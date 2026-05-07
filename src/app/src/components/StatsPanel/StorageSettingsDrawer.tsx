import { useState } from "react";
import { Box, Button, Drawer, ScrollArea } from "@mantine/core";
import { IconDeviceFloppy, IconSettings } from "@tabler/icons-react";
import { useUpdateStorageSettings } from "@/hooks/useUpdateStorageSettings";
import type { StorageProfileSettings } from "@/types/stats";
import type { UpdateStorageSettingsRequest } from "@/types/settings";
import { DrawerHeader } from "@/components/DetailDrawer/DrawerHeader";
import { DrawerFooter } from "@/components/DetailDrawer/DrawerFooter";
import { StorageSettingsForm } from "./StorageSettingsForm";

const FORM_ID = "storage-settings-form";

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

  const saveButton = (
    <Button
      type="submit"
      form={FORM_ID}
      loading={mutation.isPending}
      leftSection={<IconDeviceFloppy size={16} />}
      size="sm"
    >
      Save Changes
    </Button>
  );

  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      position="right"
      size="md"
      withCloseButton={false}
      styles={{
        body: {
          padding: 0,
          display: "flex",
          flexDirection: "column",
          height: "100%",
        },
      }}
    >
      <DrawerHeader
        icon={<IconSettings size={20} />}
        title="Storage Settings"
        description="Changes are prospective only — existing data is not auto-pruned."
      />
      <ScrollArea style={{ flex: 1 }}>
        <Box p="md">
          <StorageSettingsForm
            formId={FORM_ID}
            currentSettings={currentSettings}
            onSuccess={onClose}
            onSubmit={handleSubmit}
            isSubmitting={mutation.isPending}
            submitError={submitError}
          />
        </Box>
      </ScrollArea>
      <DrawerFooter onBack={onClose} rightSection={saveButton} />
    </Drawer>
  );
}
