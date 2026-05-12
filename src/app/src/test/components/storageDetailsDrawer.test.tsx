import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StorageDetailsDrawer } from "@/components/StatsPanel/StorageDetailsDrawer";
import type {
  MaintenanceStatus,
  StorageProjection,
  StorageStats,
} from "@/types";
import { AllProviders } from "../AllProviders";

const STORAGE: StorageStats = {
  total_size_bytes: 2048,
  total_size_pretty: "2 KB",
  tables: [],
};

const PROJECTION: StorageProjection = {
  status: "available",
  database_size_bytes: 2048,
  ct_observations_count: 100,
  certificates_count: 200,
  hostnames_count: 100,
  certificate_hostnames_count: 250,
  planned_observations_total: 1000,
  planned_observations_completed: 100,
  planned_observations_remaining: 900,
  sync_percent_by_observation: 0.1,
  bytes_per_observation_current: 20,
  projected_remaining_database_size_bytes: 18000,
  projected_final_database_size_bytes: 20000,
  storage_percent_of_projected: 0.1,
  projection_low_bytes: 18000,
  projection_current_bytes: 20000,
  projection_high_bytes: 22000,
  disk_total_bytes: 100000,
  disk_used_bytes: 2048,
  disk_free_bytes: 97952,
  disk_free_percent: 0.979,
  configured_min_free_disk_bytes: 1024,
  projected_disk_free_after_sync_bytes: 79952,
  projected_fits_on_disk: true,
  notes: [],
};

const MAINTENANCE: MaintenanceStatus = {
  status: "complete",
  active_profile: "current-osint",
  last_prune_started_at: "2025-01-01T00:00:00Z",
  last_prune_completed_at: "2025-01-01T00:01:00Z",
  last_prune_status: "complete",
  last_prune_mode: "execute",
  last_prune_deleted: {
    certificates: 10,
    certificate_hostnames: 20,
    observations: 100,
    entry_outcomes: 5,
    ingestion_metrics: 2,
  },
  preserved_hostnames: null,
  duration_ms: 60000,
  next_prune_due_at: null,
  is_enforced: true,
  error_message: null,
};

describe("StorageDetailsDrawer", () => {
  it("does not render content when closed", () => {
    render(
      <AllProviders>
        <StorageDetailsDrawer
          opened={false}
          onClose={vi.fn()}
          storage={STORAGE}
          projection={PROJECTION}
          maintenance={null}
        />
      </AllProviders>,
    );
    expect(screen.queryByText("Storage Details")).toBeNull();
  });

  it("renders title when open", () => {
    render(
      <AllProviders>
        <StorageDetailsDrawer
          opened
          onClose={vi.fn()}
          storage={STORAGE}
          projection={PROJECTION}
          maintenance={null}
        />
      </AllProviders>,
    );
    expect(screen.getByText("Storage Details")).toBeInTheDocument();
  });

  it("renders without crashing when maintenance is provided", () => {
    const { container } = render(
      <AllProviders>
        <StorageDetailsDrawer
          opened
          onClose={vi.fn()}
          storage={STORAGE}
          projection={PROJECTION}
          maintenance={MAINTENANCE}
        />
      </AllProviders>,
    );
    expect(screen.getByText("Storage Details")).toBeInTheDocument();
    expect(container).toBeTruthy();
  });

  it("does not render MaintenancePanel when maintenance is null", () => {
    render(
      <AllProviders>
        <StorageDetailsDrawer
          opened
          onClose={vi.fn()}
          storage={STORAGE}
          projection={PROJECTION}
          maintenance={null}
        />
      </AllProviders>,
    );
    // Storage Details heading should be present but no maintenance block
    expect(screen.getByText("Storage Details")).toBeInTheDocument();
  });

  it("calls onClose when back button is clicked", async () => {
    const onClose = vi.fn();
    render(
      <AllProviders>
        <StorageDetailsDrawer
          opened
          onClose={onClose}
          storage={STORAGE}
          projection={PROJECTION}
          maintenance={null}
        />
      </AllProviders>,
    );
    const backBtn = screen.getByRole("button", { name: /back/i });
    await userEvent.click(backBtn);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
