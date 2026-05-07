import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SettingsPage } from "@/pages/SettingsPage/SettingsPage";
import { useStorageSettings } from "@/hooks/useStorageSettings";
import { ApiError } from "@/services/apiClient";
import { AllProviders } from "../AllProviders";

vi.mock("@/hooks/useStorageSettings", () => ({
  useStorageSettings: vi.fn(),
}));

vi.mock("@/services/settingsApi", () => ({
  getStorageSettingsHistory: vi.fn().mockResolvedValue([]),
  SETTINGS_QUERY_KEYS: {
    storageSettings: ["settings", "storage"],
    storageSettingsHistory: ["settings", "storage", "history"],
  },
}));

vi.mock("@/hooks/useUpdateStorageSettings", () => ({
  useUpdateStorageSettings: vi.fn().mockReturnValue({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

const mockUseStorageSettings = vi.mocked(useStorageSettings);

const SETTINGS_FIXTURE = {
  storage_profile: "standard",
  cert_storage_mode: "fingerprint_only",
  hostname_retention_mode: "rolling",
  backfill_days: 90,
  cert_retention_days: 365,
  observation_retention_days: 90,
  entry_outcome_retention_days: 7,
  metrics_retention_days: 90,
  settings_hash: "abc123def456",
  updated_at: "2025-01-15T12:00:00Z",
  updated_by: "admin",
  source: "database" as const,
};

beforeEach(() => {
  mockUseStorageSettings.mockReturnValue({
    data: undefined,
    isLoading: true,
    isError: false,
  } as unknown as ReturnType<typeof useStorageSettings>);
});

function renderPage() {
  return render(
    <AllProviders initialEntries={["/settings"]}>
      <SettingsPage />
    </AllProviders>,
  );
}

describe("SettingsPage loading state", () => {
  it("renders without crashing when loading", () => {
    const { container } = renderPage();
    expect(container).toBeTruthy();
  });
});

describe("SettingsPage with data", () => {
  beforeEach(() => {
    mockUseStorageSettings.mockReturnValue({
      data: SETTINGS_FIXTURE,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useStorageSettings>);
  });

  it("renders Settings page title", () => {
    renderPage();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders Storage Profile section heading", () => {
    renderPage();
    expect(screen.getByText("Storage Profile")).toBeInTheDocument();
  });

  it("renders the active profile badge", () => {
    renderPage();
    expect(screen.getByText("standard")).toBeInTheDocument();
  });

  it("renders the Edit button to open settings drawer", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
  });

  it("renders last updated metadata", () => {
    renderPage();
    expect(screen.getByText(/Last updated/i)).toBeInTheDocument();
  });

  it("renders retention field values", () => {
    renderPage();
    expect(screen.getByText("fingerprint_only")).toBeInTheDocument();
    expect(screen.getByText("90")).toBeInTheDocument();
  });
});

describe("SettingsPage error state", () => {
  it("renders not-bootstrapped state on 404", () => {
    const notFoundError = new ApiError(404, "No storage settings found.");
    mockUseStorageSettings.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: notFoundError,
    } as unknown as ReturnType<typeof useStorageSettings>);
    renderPage();
    expect(screen.getByText(/not been initialised yet/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /configure/i }),
    ).toBeInTheDocument();
  });

  it("renders generic error alert on non-404 failures", () => {
    const serverError = new ApiError(500, "Internal server error");
    mockUseStorageSettings.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: serverError,
    } as unknown as ReturnType<typeof useStorageSettings>);
    renderPage();
    expect(
      screen.getByText(/could not load storage settings/i),
    ).toBeInTheDocument();
  });
});
