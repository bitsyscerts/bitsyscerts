import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { IndexerActivitySummary } from "@/components/StatsPanel/IndexerActivitySummary";
import type { IngestionRateStats, WorkerSummary } from "@/types";
import { AllProviders } from "../AllProviders";

const WORKERS: WorkerSummary = {
  active_total: 3,
  stale_total: 0,
  tail_active: 2,
  backfill_active: 1,
  stats_active: 0,
  maintenance_active: 0,
  unknown_active: 0,
  items: [],
};

const RATE_STATS: IngestionRateStats = {
  windows: [
    {
      window_seconds: 300,
      observations_per_sec: 5,
      observations_per_min: 300,
      certs_per_min: 2,
      hostnames_per_min: 3,
    },
  ],
};

const EMPTY_RATE: IngestionRateStats = { windows: [] };

describe("IndexerActivitySummary", () => {
  it("renders active worker count when workers are provided", () => {
    render(
      <AllProviders>
        <IndexerActivitySummary
          workers={WORKERS}
          ingestionRate={RATE_STATS}
          onInspectWorkers={vi.fn()}
        />
      </AllProviders>,
    );
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders tail / backfill counts", () => {
    render(
      <AllProviders>
        <IndexerActivitySummary
          workers={WORKERS}
          ingestionRate={EMPTY_RATE}
          onInspectWorkers={vi.fn()}
        />
      </AllProviders>,
    );
    expect(screen.getByText("2 / 1")).toBeInTheDocument();
  });

  it("shows stale badge when stale workers exist", () => {
    render(
      <AllProviders>
        <IndexerActivitySummary
          workers={{ ...WORKERS, stale_total: 1 }}
          ingestionRate={EMPTY_RATE}
          onInspectWorkers={vi.fn()}
        />
      </AllProviders>,
    );
    expect(screen.getByText("1 stale")).toBeInTheDocument();
  });

  it("shows no worker data when workers is null", () => {
    render(
      <AllProviders>
        <IndexerActivitySummary
          workers={null}
          ingestionRate={EMPTY_RATE}
          onInspectWorkers={vi.fn()}
        />
      </AllProviders>,
    );
    expect(screen.getByText("No worker data")).toBeInTheDocument();
  });

  it("shows ingestion rate when rate data is available", () => {
    render(
      <AllProviders>
        <IndexerActivitySummary
          workers={null}
          ingestionRate={RATE_STATS}
          onInspectWorkers={vi.fn()}
        />
      </AllProviders>,
    );
    expect(screen.getByText(/obs\/min/i)).toBeInTheDocument();
  });

  it("calls onInspectWorkers when inspect button is clicked", () => {
    const onInspectWorkers = vi.fn();
    render(
      <AllProviders>
        <IndexerActivitySummary
          workers={null}
          ingestionRate={EMPTY_RATE}
          onInspectWorkers={onInspectWorkers}
        />
      </AllProviders>,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /inspect workers/i }),
    );
    expect(onInspectWorkers).toHaveBeenCalledOnce();
  });
});
