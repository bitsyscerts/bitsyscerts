import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { IngestionRateCard } from "@/components/StatsPanel/IngestionRateCard";
import type { IngestionRateStats } from "@/types";
import { AllProviders } from "../AllProviders";

function makeRate(
  overrides: Partial<IngestionRateStats> = {},
): IngestionRateStats {
  return {
    windows: [
      {
        window_seconds: 300,
        observations_per_sec: 2.5,
        certs_per_min: 15.0,
        hostnames_per_min: 8.0,
      },
    ],
    ...overrides,
  };
}

describe("IngestionRateCard", () => {
  it("renders the card heading", () => {
    render(
      <AllProviders>
        <IngestionRateCard ingestionRate={makeRate()} />
      </AllProviders>,
    );
    expect(screen.getByText("Ingestion Rate")).toBeInTheDocument();
  });

  it("renders observations/sec from window data", () => {
    render(
      <AllProviders>
        <IngestionRateCard ingestionRate={makeRate()} />
      </AllProviders>,
    );
    expect(screen.getByText("2.50")).toBeInTheDocument();
  });

  it("renders 5m window label", () => {
    render(
      <AllProviders>
        <IngestionRateCard ingestionRate={makeRate()} />
      </AllProviders>,
    );
    expect(screen.getByText("5m")).toBeInTheDocument();
  });

  it("renders 1h window label for 3600 seconds", () => {
    render(
      <AllProviders>
        <IngestionRateCard
          ingestionRate={makeRate({
            windows: [
              {
                window_seconds: 3600,
                observations_per_sec: 1.0,
                certs_per_min: 5.0,
                hostnames_per_min: 2.0,
              },
            ],
          })}
        />
      </AllProviders>,
    );
    expect(screen.getByText("1h")).toBeInTheDocument();
  });

  it("renders zero rates without error", () => {
    render(
      <AllProviders>
        <IngestionRateCard
          ingestionRate={makeRate({
            windows: [
              {
                window_seconds: 300,
                observations_per_sec: 0,
                certs_per_min: 0,
                hostnames_per_min: 0,
              },
            ],
          })}
        />
      </AllProviders>,
    );
    expect(screen.getByText("0.00")).toBeInTheDocument();
  });
});
