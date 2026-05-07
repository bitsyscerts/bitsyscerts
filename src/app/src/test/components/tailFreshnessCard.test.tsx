import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TailFreshnessCard } from "@/components/StatsPanel/TailFreshnessCard";
import type { TailFreshnessStats } from "@/types";
import { AllProviders } from "../AllProviders";

function makeFreshness(
  overrides: Partial<TailFreshnessStats> = {},
): TailFreshnessStats {
  return {
    stale_threshold_seconds: 300,
    stale_log_count: 0,
    oldest_lag_seconds: 45,
    median_lag_seconds: 20,
    ...overrides,
  };
}

describe("TailFreshnessCard", () => {
  it("renders card heading", () => {
    render(
      <AllProviders>
        <TailFreshnessCard tailFreshness={makeFreshness()} />
      </AllProviders>,
    );
    expect(screen.getByText("Tail Freshness")).toBeInTheDocument();
  });

  it("shows all fresh badge when stale count is zero", () => {
    render(
      <AllProviders>
        <TailFreshnessCard
          tailFreshness={makeFreshness({ stale_log_count: 0 })}
        />
      </AllProviders>,
    );
    expect(screen.getByText("all fresh")).toBeInTheDocument();
  });

  it("shows stale badge with count when stale logs exist", () => {
    render(
      <AllProviders>
        <TailFreshnessCard
          tailFreshness={makeFreshness({ stale_log_count: 3 })}
        />
      </AllProviders>,
    );
    expect(screen.getByText("3 stale")).toBeInTheDocument();
  });

  it("renders alert when stale logs exist", () => {
    render(
      <AllProviders>
        <TailFreshnessCard
          tailFreshness={makeFreshness({
            stale_log_count: 2,
            oldest_lag_seconds: 600,
          })}
        />
      </AllProviders>,
    );
    expect(screen.getByText(/2 logs have not synced/i)).toBeInTheDocument();
  });

  it("does not render alert when all logs are fresh", () => {
    render(
      <AllProviders>
        <TailFreshnessCard
          tailFreshness={makeFreshness({ stale_log_count: 0 })}
        />
      </AllProviders>,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders dash for null lag values", () => {
    render(
      <AllProviders>
        <TailFreshnessCard
          tailFreshness={makeFreshness({
            oldest_lag_seconds: null,
            median_lag_seconds: null,
          })}
        />
      </AllProviders>,
    );
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(2);
  });
});
