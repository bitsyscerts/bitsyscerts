import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";
import { BackfillWorkloadSection } from "@/components/StatsPanel/BackfillWorkloadSection";
import type { IngestionWorkload } from "@/types";

function wrapper({ children }: { children: ReactNode }) {
  return <MantineProvider>{children}</MantineProvider>;
}

const BASE_WORKLOAD: IngestionWorkload = {
  planned_observations_total: 1000,
  planned_observations_completed: 500,
  planned_observations_remaining: 500,
  sync_percent: 0.5,
};

describe("BackfillWorkloadSection", () => {
  it("renders the section heading", () => {
    render(<BackfillWorkloadSection workload={BASE_WORKLOAD} />, { wrapper });
    expect(screen.getByText("Backfill workload")).toBeInTheDocument();
  });

  it("renders a progress bar with correct aria-label", () => {
    render(<BackfillWorkloadSection workload={BASE_WORKLOAD} />, { wrapper });
    expect(
      screen.getByRole("progressbar", { name: /backfill progress/i }),
    ).toBeInTheDocument();
  });

  it("renders correctly when sync_percent is null", () => {
    const workload: IngestionWorkload = {
      ...BASE_WORKLOAD,
      sync_percent: null,
    };
    render(<BackfillWorkloadSection workload={workload} />, { wrapper });
    expect(screen.getByText("Backfill workload")).toBeInTheDocument();
  });
});
