import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DbContentionCard } from "@/components/StatsPanel/DbContentionCard";
import type { DbContentionStats } from "@/types";
import { AllProviders } from "../AllProviders";

function makeContention(
  overrides: Partial<DbContentionStats> = {},
): DbContentionStats {
  return {
    status: "throttling",
    degraded_mode_active: false,
    pressure_ema: 0.27,
    base_sleep_seconds: 0.5,
    shared_batch_size_cap: 32,
    effective_batch_size_cap: 32,
    updated_at: "2025-01-01T00:00:00Z",
    notes: ["Shared DB contention throttling is currently active."],
    total_retryable_errors: 0,
    retryable_errors_per_min_5min: null,
    ...overrides,
  };
}

describe("DbContentionCard", () => {
  it("renders shared DB contention metrics", () => {
    render(
      <AllProviders>
        <DbContentionCard contention={makeContention()} />
      </AllProviders>,
    );

    expect(screen.getByText("DB Contention Control")).toBeInTheDocument();
    expect(screen.getByText("throttling")).toBeInTheDocument();
    expect(screen.getByText("0.270")).toBeInTheDocument();
    expect(screen.getByText("0.50 s")).toBeInTheDocument();
    expect(
      screen.getByText(/Shared DB contention throttling is currently active/i),
    ).toBeInTheDocument();
  });

  it("renders degraded messaging for stale control state", () => {
    render(
      <AllProviders>
        <DbContentionCard
          contention={makeContention({
            status: "stale",
            degraded_mode_active: true,
            effective_batch_size_cap: null,
            notes: [
              "Shared contention state is stale; workers fall back to local conservative pacing when coordination is unavailable.",
            ],
          })}
        />
      </AllProviders>,
    );

    expect(screen.getByText("stale")).toBeInTheDocument();
    expect(
      screen.getByText(/workers fall back to local conservative pacing/i),
    ).toBeInTheDocument();
  });

  it("renders total retryable errors and 5m rate when present", () => {
    render(
      <AllProviders>
        <DbContentionCard
          contention={makeContention({
            total_retryable_errors: 42,
            retryable_errors_per_min_5min: 2.5,
          })}
        />
      </AllProviders>,
    );

    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("2.50/min")).toBeInTheDocument();
  });

  it("renders dash for retry rate when null", () => {
    render(
      <AllProviders>
        <DbContentionCard
          contention={makeContention({ retryable_errors_per_min_5min: null })}
        />
      </AllProviders>,
    );

    expect(screen.getByText("Retry rate (5m)")).toBeInTheDocument();
  });
});
