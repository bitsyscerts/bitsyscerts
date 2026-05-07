import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { StorageSettingsForm } from "@/components/StatsPanel/StorageSettingsForm";
import type { StorageProfileSettings } from "@/types/stats";
import { AllProviders } from "../AllProviders";

function noop() {
  return Promise.resolve();
}

function makeSettings(
  overrides: Partial<StorageProfileSettings> = {},
): StorageProfileSettings {
  return {
    storage_profile: "standard",
    cert_storage_mode: "metadata_spki",
    hostname_retention_mode: "forever",
    backfill_days: 90,
    cert_retention_days: 90,
    observation_retention_days: 90,
    entry_outcome_retention_days: 90,
    metrics_retention_days: 30,
    settings_hash: "abc123",
    source: "database",
    ...overrides,
  };
}

function renderForm(settings?: StorageProfileSettings | null) {
  const onSubmit = vi.fn(noop);
  const onSuccess = vi.fn();
  render(
    <AllProviders>
      <StorageSettingsForm
        formId="test-form"
        currentSettings={settings}
        onSuccess={onSuccess}
        onSubmit={onSubmit}
        isSubmitting={false}
        submitError={null}
      />
    </AllProviders>,
  );
  return { onSubmit, onSuccess };
}

describe("StorageSettingsForm — field lock behaviour", () => {
  it("disables sub-fields when a preset profile is selected", () => {
    renderForm(makeSettings({ storage_profile: "standard" }));

    expect(
      screen.getByRole("textbox", { name: /backfill days/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: /certificate retention/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: /observation retention/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: /entry outcome retention/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: /metrics retention/i }),
    ).toBeDisabled();
  });

  it("enables sub-fields when the custom profile is selected", () => {
    renderForm(makeSettings({ storage_profile: "custom" }));

    expect(
      screen.getByRole("textbox", { name: /backfill days/i }),
    ).not.toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: /certificate retention/i }),
    ).not.toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: /observation retention/i }),
    ).not.toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: /entry outcome retention/i }),
    ).not.toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: /metrics retention/i }),
    ).not.toBeDisabled();
  });

  it("all preset profiles disable sub-fields on initial render", () => {
    for (const profile of ["lite", "standard", "research", "archive"]) {
      const { unmount } = render(
        <AllProviders>
          <StorageSettingsForm
            formId="test-form"
            currentSettings={makeSettings({ storage_profile: profile })}
            onSuccess={vi.fn()}
            onSubmit={vi.fn(noop)}
            isSubmitting={false}
            submitError={null}
          />
        </AllProviders>,
      );
      expect(
        screen.getByRole("textbox", { name: /backfill days/i }),
      ).toBeDisabled();
      unmount();
    }
  });

  it("shows the archive DER warning only for the archive profile", () => {
    const { unmount: unmountArchive } = render(
      <AllProviders>
        <StorageSettingsForm
          formId="test-form"
          currentSettings={makeSettings({ storage_profile: "archive" })}
          onSuccess={vi.fn()}
          onSubmit={vi.fn(noop)}
          isSubmitting={false}
          submitError={null}
        />
      </AllProviders>,
    );
    expect(
      screen.getByText(/stores full DER certificates/i),
    ).toBeInTheDocument();
    unmountArchive();

    render(
      <AllProviders>
        <StorageSettingsForm
          formId="test-form"
          currentSettings={makeSettings({ storage_profile: "standard" })}
          onSuccess={vi.fn()}
          onSubmit={vi.fn(noop)}
          isSubmitting={false}
          submitError={null}
        />
      </AllProviders>,
    );
    expect(
      screen.queryByText(/stores full DER certificates/i),
    ).not.toBeInTheDocument();
  });

  it("shows submit error alert when submitError is set", () => {
    render(
      <AllProviders>
        <StorageSettingsForm
          formId="test-form"
          currentSettings={makeSettings({ storage_profile: "custom" })}
          onSuccess={vi.fn()}
          onSubmit={vi.fn(noop)}
          isSubmitting={false}
          submitError="Something went wrong"
        />
      </AllProviders>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("calls onSubmit with form values when submitted", async () => {
    const onSubmit = vi.fn(noop);
    render(
      <AllProviders>
        <StorageSettingsForm
          formId="test-form"
          currentSettings={makeSettings({ storage_profile: "custom" })}
          onSuccess={vi.fn()}
          onSubmit={onSubmit}
          isSubmitting={false}
          submitError={null}
        />
      </AllProviders>,
    );
    const form = document.getElementById("test-form");
    fireEvent.submit(form as HTMLElement);
    await vi.waitFor(() => {
      expect(onSubmit).toHaveBeenCalledOnce();
    });
  });

  it("updates a numeric field value in custom mode", () => {
    render(
      <AllProviders>
        <StorageSettingsForm
          formId="test-form"
          currentSettings={makeSettings({ storage_profile: "custom" })}
          onSuccess={vi.fn()}
          onSubmit={vi.fn(noop)}
          isSubmitting={false}
          submitError={null}
        />
      </AllProviders>,
    );
    const backfillInput = screen.getByRole("textbox", {
      name: /backfill days/i,
    });
    fireEvent.change(backfillInput, { target: { value: "60" } });
    expect(backfillInput).toHaveValue("60");
  });

  it("can toggle the archive explicit opt-in checkbox", () => {
    render(
      <AllProviders>
        <StorageSettingsForm
          formId="test-form"
          currentSettings={makeSettings({ storage_profile: "archive" })}
          onSuccess={vi.fn()}
          onSubmit={vi.fn(noop)}
          isSubmitting={false}
          submitError={null}
        />
      </AllProviders>,
    );
    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).not.toBeChecked();
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });
});
