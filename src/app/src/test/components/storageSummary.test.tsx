import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StorageSummary } from "@/components/StatsPanel/StorageSummary";
import type {
  MaintenanceStatus,
  StorageProfileSettings,
  StorageStats,
} from "@/types";
import { AllProviders } from "../AllProviders";

const STORAGE: StorageStats = {
  total_size_bytes: 5120,
  total_size_pretty: "5 KB",
  tables: [],
};

const PROFILE: StorageProfileSettings = {
  storage_profile: "current-osint",
  cert_storage_mode: "fingerprint_only",
  hostname_retention_mode: "rolling_window",
  backfill_days: 90,
  cert_retention_days: 180,
  observation_retention_days: 60,
  entry_outcome_retention_days: 30,
  metrics_retention_days: 90,
  settings_hash: "abc123",
  source: "database",
};

const MAINTENANCE_COMPLETE: MaintenanceStatus = {
  status: "complete",
  active_profile: "current-osint",
  last_prune_started_at: "2025-01-01T00:00:00Z",
  last_prune_completed_at: "2025-01-01T00:01:00Z",
  last_prune_status: "complete",
  last_prune_mode: "execute",
  last_prune_deleted: {
    certificates: 0,
    certificate_hostnames: 0,
    observations: 0,
    entry_outcomes: 0,
    ingestion_metrics: 0,
  },
  preserved_hostnames: null,
  duration_ms: 1000,
  next_prune_due_at: null,
  is_enforced: true,
  error_message: null,
};

describe("StorageSummary", () => {
  it("renders total storage size", () => {
    render(
      <AllProviders>
        <StorageSummary
          storage={STORAGE}
          storageProfile={null}
          maintenance={null}
          onStorageDetails={vi.fn()}
        />
      </AllProviders>,
    );
    expect(screen.getByText("5 KB")).toBeInTheDocument();
  });

  it("renders profile badge when storageProfile is provided", () => {
    render(
      <AllProviders>
        <StorageSummary
          storage={STORAGE}
          storageProfile={PROFILE}
          maintenance={null}
          onStorageDetails={vi.fn()}
        />
      </AllProviders>,
    );
    expect(screen.getByText("current-osint")).toBeInTheDocument();
  });

  it("renders maintenance status Complete", () => {
    render(
      <AllProviders>
        <StorageSummary
          storage={STORAGE}
          storageProfile={null}
          maintenance={MAINTENANCE_COMPLETE}
          onStorageDetails={vi.fn()}
        />
      </AllProviders>,
    );
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it("renders maintenance status Never ran", () => {
    render(
      <AllProviders>
        <StorageSummary
          storage={STORAGE}
          storageProfile={null}
          maintenance={{ ...MAINTENANCE_COMPLETE, status: "never_ran" }}
          onStorageDetails={vi.fn()}
        />
      </AllProviders>,
    );
    expect(screen.getByText("Never ran")).toBeInTheDocument();
  });

  it("calls onStorageDetails when button is clicked", async () => {
    const onStorageDetails = vi.fn();
    render(
      <AllProviders>
        <StorageSummary
          storage={STORAGE}
          storageProfile={null}
          maintenance={null}
          onStorageDetails={onStorageDetails}
        />
      </AllProviders>,
    );
    await userEvent.click(screen.getByRole("button", { name: /storage details/i }));
    expect(onStorageDetails).toHaveBeenCalledOnce();
  });
});
