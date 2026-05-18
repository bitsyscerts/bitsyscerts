import { useEffect, useState } from "react";
import {
  Alert,
  Checkbox,
  NumberInput,
  Select,
  Stack,
  Text,
} from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import type { StorageProfileSettings } from "@/types/stats";
import type { UpdateStorageSettingsRequest } from "@/types/settings";

const PROFILE_DEFAULTS: Partial<
  Record<string, Partial<UpdateStorageSettingsRequest>>
> = {
  lite: {
    cert_storage_mode: "none",
    hostname_retention_mode: "forever",
    backfill_days: 30,
    cert_retention_days: 1,
    observation_retention_days: 7,
    entry_outcome_retention_days: 7,
    metrics_retention_days: 14,
  },
  standard: {
    cert_storage_mode: "metadata_spki",
    hostname_retention_mode: "forever",
    backfill_days: 90,
    cert_retention_days: 90,
    observation_retention_days: 90,
    entry_outcome_retention_days: 90,
    metrics_retention_days: 30,
  },
  research: {
    cert_storage_mode: "metadata_public_key",
    hostname_retention_mode: "forever",
    backfill_days: 180,
    cert_retention_days: 180,
    observation_retention_days: 180,
    entry_outcome_retention_days: 180,
    metrics_retention_days: 60,
  },
  archive: {
    cert_storage_mode: "full_der",
    hostname_retention_mode: "forever",
    backfill_days: 0,
    cert_retention_days: 0,
    observation_retention_days: 0,
    entry_outcome_retention_days: 0,
    metrics_retention_days: 90,
  },
};

const PROFILE_OPTIONS = [
  { value: "lite", label: "Lite — minimal storage, OSINT-only" },
  { value: "standard", label: "Standard — balanced metadata retention" },
  { value: "research", label: "Research — longer retention, richer metadata" },
  { value: "archive", label: "Archive — full DER storage (requires opt-in)" },
  { value: "custom", label: "Custom — manual configuration" },
];

const CERT_MODE_OPTIONS = [
  { value: "none", label: "None — no certificate data" },
  { value: "metadata_spki", label: "Metadata + SPKI" },
  { value: "metadata_public_key", label: "Metadata + public key" },
  { value: "full_der", label: "Full DER (large storage)" },
];

const HOSTNAME_RETENTION_OPTIONS = [
  { value: "forever", label: "Forever" },
  { value: "rolling", label: "Rolling window" },
];

interface FormValues extends UpdateStorageSettingsRequest {
  storage_profile: string;
}

function buildInitialValues(
  current?: StorageProfileSettings | null,
): FormValues {
  if (!current) {
    return {
      storage_profile: "lite",
      ...PROFILE_DEFAULTS.lite,
      archive_explicit_optin: false,
    } as FormValues;
  }
  return {
    storage_profile: current.storage_profile,
    cert_storage_mode: current.cert_storage_mode,
    hostname_retention_mode: current.hostname_retention_mode,
    backfill_days: current.backfill_days,
    cert_retention_days: current.cert_retention_days,
    observation_retention_days: current.observation_retention_days,
    entry_outcome_retention_days: current.entry_outcome_retention_days,
    metrics_retention_days: current.metrics_retention_days,
    archive_explicit_optin: false,
  };
}

export interface StorageSettingsFormProps {
  formId: string;
  currentSettings?: StorageProfileSettings | null;
  onSuccess: () => void;
  onSubmit: (values: UpdateStorageSettingsRequest) => Promise<void>;
  isSubmitting: boolean;
  submitError: string | null;
}

export function StorageSettingsForm({
  formId,
  currentSettings,
  onSubmit,
  isSubmitting: _isSubmitting,
  submitError,
}: StorageSettingsFormProps) {
  const [values, setValues] = useState<FormValues>(() =>
    buildInitialValues(currentSettings),
  );

  const selectedProfile = values.storage_profile;
  const isCustom = selectedProfile === "custom";

  // Auto-fill defaults when a non-custom profile is selected
  useEffect(() => {
    const defaults = PROFILE_DEFAULTS[selectedProfile];
    if (defaults !== undefined) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setValues((prev) => ({ ...prev, ...defaults }));
    }
  }, [selectedProfile]);

  function handleChange<K extends keyof FormValues>(
    key: K,
    value: FormValues[K],
  ) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.SyntheticEvent) {
    e.preventDefault();
    const { storage_profile, ...rest } = values;
    await onSubmit({ storage_profile, ...rest });
  }

  const isArchive = selectedProfile === "archive";

  return (
    <form
      id={formId}
      onSubmit={(e) => {
        void handleSubmit(e);
      }}
    >
      <Stack gap="sm">
        <Select
          label="Storage profile"
          data={PROFILE_OPTIONS}
          value={values.storage_profile}
          onChange={(v) => {
            handleChange("storage_profile", v ?? "lite");
          }}
        />
        <Select
          label="Certificate storage mode"
          data={CERT_MODE_OPTIONS}
          value={values.cert_storage_mode}
          disabled={!isCustom}
          onChange={(v) => {
            handleChange("cert_storage_mode", v ?? "none");
          }}
        />
        <Select
          label="Hostname retention mode"
          data={HOSTNAME_RETENTION_OPTIONS}
          value={values.hostname_retention_mode}
          disabled={!isCustom}
          onChange={(v) => {
            handleChange("hostname_retention_mode", v ?? "forever");
          }}
        />
        <NumberInput
          label="Backfill days"
          description="0 = unlimited"
          min={0}
          disabled={!isCustom}
          value={values.backfill_days}
          onChange={(v) => {
            handleChange("backfill_days", typeof v === "number" ? v : 0);
          }}
        />
        <NumberInput
          label="Certificate retention (days)"
          min={0}
          disabled={!isCustom}
          value={values.cert_retention_days}
          onChange={(v) => {
            handleChange("cert_retention_days", typeof v === "number" ? v : 0);
          }}
        />
        <NumberInput
          label="Observation retention (days)"
          min={0}
          disabled={!isCustom}
          value={values.observation_retention_days}
          onChange={(v) => {
            handleChange(
              "observation_retention_days",
              typeof v === "number" ? v : 0,
            );
          }}
        />
        <NumberInput
          label="Entry outcome retention (days)"
          min={0}
          disabled={!isCustom}
          value={values.entry_outcome_retention_days}
          onChange={(v) => {
            handleChange(
              "entry_outcome_retention_days",
              typeof v === "number" ? v : 0,
            );
          }}
        />
        <NumberInput
          label="Metrics retention (days)"
          min={1}
          disabled={!isCustom}
          value={values.metrics_retention_days}
          onChange={(v) => {
            handleChange(
              "metrics_retention_days",
              typeof v === "number" ? v : 1,
            );
          }}
        />

        {isArchive && (
          <Alert
            icon={<IconAlertTriangle size={16} />}
            color="red"
            variant="light"
          >
            <Stack gap="xs">
              <Text size="sm" fw={600}>
                Archive profile stores full DER certificates.
              </Text>
              <Text size="sm">
                This can consume terabytes of storage. Confirm you intend to
                enable this.
              </Text>
              <Checkbox
                label="I understand this profile stores full certificates"
                checked={values.archive_explicit_optin ?? false}
                onChange={(e) => {
                  handleChange(
                    "archive_explicit_optin",
                    e.currentTarget.checked,
                  );
                }}
              />
            </Stack>
          </Alert>
        )}

        {submitError ? (
          <Alert color="red" variant="light">
            {submitError}
          </Alert>
        ) : null}
      </Stack>
    </form>
  );
}
