import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";
import { MaintenancePanel } from "@/components/StatsPanel/MaintenancePanel";
import type { MaintenanceStatus } from "@/types";

function wrapper({ children }: { children: ReactNode }) {
  return <MantineProvider>{children}</MantineProvider>;
}

function makeStatus(
  overrides: Partial<MaintenanceStatus> = {},
): MaintenanceStatus {
  return {
    status: "complete",
    active_profile: "lite",
    last_prune_started_at: new Date().toISOString(),
    last_prune_completed_at: new Date().toISOString(),
    last_prune_status: "complete",
    last_prune_mode: "execute",
    last_prune_deleted: {
      certificates: 12,
      certificate_hostnames: 3,
      observations: 99,
      entry_outcomes: 45,
      ingestion_metrics: 1,
    },
    preserved_hostnames: 1234,
    duration_ms: 250,
    next_prune_due_at: new Date(Date.now() + 3600 * 1000).toISOString(),
    is_enforced: true,
    error_message: null,
    ...overrides,
  };
}

describe("MaintenancePanel", () => {
  it("renders the enforced badge and deletion totals when complete", () => {
    render(<MaintenancePanel maintenance={makeStatus()} />, { wrapper });
    expect(screen.getByText("Retention Maintenance")).toBeInTheDocument();
    expect(
      screen.getByText("lite profile is being enforced"),
    ).toBeInTheDocument();
    expect(screen.getByText("Certificates")).toBeInTheDocument();
    expect(screen.getByText("99")).toBeInTheDocument();
  });

  it("renders the never-ran warning when status is never_ran", () => {
    render(
      <MaintenancePanel
        maintenance={makeStatus({
          status: "never_ran",
          is_enforced: false,
          last_prune_status: null,
          last_prune_completed_at: null,
        })}
      />,
      { wrapper },
    );
    expect(
      screen.getByText(/Retention maintenance has not run yet/),
    ).toBeInTheDocument();
  });

  it("renders the failure alert when last prune failed", () => {
    render(
      <MaintenancePanel
        maintenance={makeStatus({
          status: "failed",
          is_enforced: false,
          last_prune_status: "failed",
          error_message: "boom",
        })}
      />,
      { wrapper },
    );
    expect(
      screen.getByText("retention maintenance failed"),
    ).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();
  });
});
