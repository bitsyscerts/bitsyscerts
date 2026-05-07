import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { LogSyncStatus } from "@/components/StatsPanel/LogSyncStatus";
import { AllProviders } from "../AllProviders";

describe("LogSyncStatus", () => {
  it("renders History and Live pills when fully synced", () => {
    render(
      <AllProviders>
        <LogSyncStatus backfillPct={100} lagSeconds={60} />
      </AllProviders>,
    );
    expect(screen.getByText("✓ History")).toBeInTheDocument();
    expect(screen.getByText("● Live")).toBeInTheDocument();
  });

  it("renders amber history pill with percentage when backfill incomplete", () => {
    render(
      <AllProviders>
        <LogSyncStatus backfillPct={57.3} lagSeconds={30} />
      </AllProviders>,
    );
    expect(screen.getByText(/57/)).toBeInTheDocument();
    expect(screen.getByText("● Live")).toBeInTheDocument();
  });

  it("renders stale live pill with lag when tail is behind", () => {
    render(
      <AllProviders>
        <LogSyncStatus backfillPct={100} lagSeconds={600} />
      </AllProviders>,
    );
    expect(screen.getByText("✓ History")).toBeInTheDocument();
    expect(screen.getByText(/⏳/)).toBeInTheDocument();
    expect(screen.getByText(/10m/)).toBeInTheDocument();
  });

  it("renders both pills in worst case (incomplete backfill + stale tail)", () => {
    render(
      <AllProviders>
        <LogSyncStatus backfillPct={30} lagSeconds={900} />
      </AllProviders>,
    );
    expect(screen.getByText(/30/)).toBeInTheDocument();
    expect(screen.getByText(/⏳/)).toBeInTheDocument();
  });

  it("renders '? Unseen' pill in gray when lag is null", () => {
    render(
      <AllProviders>
        <LogSyncStatus backfillPct={100} lagSeconds={null} />
      </AllProviders>,
    );
    expect(screen.getByText("✓ History")).toBeInTheDocument();
    expect(screen.getByText("? Unseen")).toBeInTheDocument();
    expect(screen.queryByText("● Live")).not.toBeInTheDocument();
  });

  it("renders '? Unseen' even when backfillPct is also null", () => {
    render(
      <AllProviders>
        <LogSyncStatus backfillPct={null} lagSeconds={null} />
      </AllProviders>,
    );
    expect(screen.queryByText(/History/)).not.toBeInTheDocument();
    expect(screen.getByText("? Unseen")).toBeInTheDocument();
  });
});
