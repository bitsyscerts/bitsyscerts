import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { IndexSummary } from "@/components/StatsPanel/IndexSummary";
import type { SnapshotMetadata } from "@/types";
import { AllProviders } from "../AllProviders";

const FRESH_SNAPSHOT: SnapshotMetadata = {
  generated_at: "2025-01-01T00:00:00Z",
  age_seconds: 30,
  is_stale: false,
  stale_threshold_seconds: 300,
  source: "snapshot",
};

const STALE_SNAPSHOT: SnapshotMetadata = {
  ...FRESH_SNAPSHOT,
  is_stale: true,
};

describe("IndexSummary", () => {
  it("renders hostname, certificate, and log counts", () => {
    render(
      <AllProviders>
        <IndexSummary
          totalHostnames={12345}
          totalCertificates={67890}
          totalLogs={7}
          snapshot={FRESH_SNAPSHOT}
          onInspectLogs={vi.fn()}
        />
      </AllProviders>,
    );
    expect(screen.getByText("12,345")).toBeInTheDocument();
    expect(screen.getByText("67,890")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("shows stale snapshot indicator when snapshot is stale", () => {
    render(
      <AllProviders>
        <IndexSummary
          totalHostnames={0}
          totalCertificates={0}
          totalLogs={0}
          snapshot={STALE_SNAPSHOT}
          onInspectLogs={vi.fn()}
        />
      </AllProviders>,
    );
    expect(screen.getByText("Snapshot stale")).toBeInTheDocument();
  });

  it("shows no snapshot text when snapshot is null", () => {
    render(
      <AllProviders>
        <IndexSummary
          totalHostnames={0}
          totalCertificates={0}
          totalLogs={0}
          snapshot={null}
          onInspectLogs={vi.fn()}
        />
      </AllProviders>,
    );
    expect(screen.getByText("No snapshot yet")).toBeInTheDocument();
  });

  it("calls onInspectLogs when button is clicked", () => {
    const onInspectLogs = vi.fn();
    render(
      <AllProviders>
        <IndexSummary
          totalHostnames={0}
          totalCertificates={0}
          totalLogs={0}
          snapshot={null}
          onInspectLogs={onInspectLogs}
        />
      </AllProviders>,
    );
    fireEvent.click(screen.getByRole("button", { name: /inspect ct logs/i }));
    expect(onInspectLogs).toHaveBeenCalledOnce();
  });
});
