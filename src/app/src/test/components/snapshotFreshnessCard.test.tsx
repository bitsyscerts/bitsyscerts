import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SnapshotFreshnessCard } from "@/components/StatsPanel/SnapshotFreshnessCard";
import type { SnapshotMetadata } from "@/types";
import { AllProviders } from "../AllProviders";

function snapshot(overrides: Partial<SnapshotMetadata> = {}): SnapshotMetadata {
  return {
    generated_at: "2026-05-09T12:00:00Z",
    age_seconds: 8,
    is_stale: false,
    stale_threshold_seconds: 120,
    source: "snapshot",
    ...overrides,
  };
}

describe("SnapshotFreshnessCard (Sprint 5)", () => {
  it("renders Updated Xs ago when fresh", () => {
    render(
      <AllProviders>
        <SnapshotFreshnessCard snapshot={snapshot()} />
      </AllProviders>,
    );
    expect(screen.getByTestId("snapshot-freshness-fresh")).toBeInTheDocument();
    expect(screen.getByText(/Updated 8s ago/)).toBeInTheDocument();
  });

  it("renders the stale warning when is_stale=true", () => {
    render(
      <AllProviders>
        <SnapshotFreshnessCard
          snapshot={snapshot({ age_seconds: 252, is_stale: true })}
        />
      </AllProviders>,
    );
    expect(screen.getByTestId("snapshot-freshness-stale")).toBeInTheDocument();
    expect(screen.getByText(/Stats stale/)).toBeInTheDocument();
  });

  it("renders the no-snapshot notice when source is none", () => {
    render(
      <AllProviders>
        <SnapshotFreshnessCard
          snapshot={snapshot({ age_seconds: null, source: "none" })}
        />
      </AllProviders>,
    );
    expect(screen.getByTestId("snapshot-freshness-none")).toBeInTheDocument();
    expect(
      screen.getByText(/Stats snapshot has not been generated yet/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /The stats snapshotter service should create one shortly/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/docker compose run --rm migrate ctpool stats-snapshot/),
    ).toBeInTheDocument();
  });

  it("renders the no-snapshot notice when snapshot is null", () => {
    render(
      <AllProviders>
        <SnapshotFreshnessCard snapshot={null} />
      </AllProviders>,
    );
    expect(screen.getByTestId("snapshot-freshness-none")).toBeInTheDocument();
  });
});
