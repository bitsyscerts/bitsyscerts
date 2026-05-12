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
    expect(
      screen.getByText(/High duplicate throughput is normal/i),
    ).toBeInTheDocument();
  });

  it("renders observations/sec from window data", () => {
    // Sprint 5: card now exposes "Observations/min" — derived from
    // observations_per_sec * 60 when observations_per_min is absent.
    render(
      <AllProviders>
        <IngestionRateCard ingestionRate={makeRate()} />
      </AllProviders>,
    );
    // 2.5/sec * 60 = 150/min
    expect(screen.getByText("150.00/min")).toBeInTheDocument();
    expect(screen.getByText("Observations/min")).toBeInTheDocument();
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
    // Sprint 5: zero throughput renders precise per-min label values.
    expect(screen.getAllByText("0.00/min").length).toBeGreaterThan(0);
  });

  it("hides uniqueness rows when fields are absent (Sprint 5)", () => {
    render(
      <AllProviders>
        <IngestionRateCard ingestionRate={makeRate()} />
      </AllProviders>,
    );
    expect(screen.queryByText("New certs/min")).not.toBeInTheDocument();
    expect(screen.queryByText("Duplicate certs/min")).not.toBeInTheDocument();
    expect(screen.queryByText("New hostnames/min")).not.toBeInTheDocument();
  });

  it("renders uniqueness rows when fields are populated (Sprint 5)", () => {
    render(
      <AllProviders>
        <IngestionRateCard
          ingestionRate={{
            windows: [
              {
                window_seconds: 300,
                observations_per_sec: 2.5,
                certs_per_min: 15.0,
                hostnames_per_min: 8.0,
                new_unique_certificates_per_min: 1.0,
                duplicate_certificates_per_min: 14.0,
                new_unique_hostnames_per_min: 0.5,
                known_hostnames_per_min: 7.5,
              },
            ],
          }}
        />
      </AllProviders>,
    );
    expect(screen.getByText("New certs/min")).toBeInTheDocument();
    expect(screen.getByText("Duplicate certs/min")).toBeInTheDocument();
    expect(screen.getByText("New hostnames/min")).toBeInTheDocument();
  });
});
