import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SystemStatusCard } from "@/components/StatsPanel/SystemStatusCard";
import { AllProviders } from "../AllProviders";

describe("SystemStatusCard", () => {
  it("renders healthy label", () => {
    render(
      <AllProviders>
        <SystemStatusCard level="healthy" issueCount={0} />
      </AllProviders>,
    );
    expect(screen.getByText("All systems healthy")).toBeInTheDocument();
    expect(screen.queryByText(/issue/)).toBeNull();
  });

  it("renders warning label", () => {
    render(
      <AllProviders>
        <SystemStatusCard level="warning" issueCount={2} />
      </AllProviders>,
    );
    expect(screen.getByText("Warnings detected")).toBeInTheDocument();
    expect(screen.getByText("2 issues detected")).toBeInTheDocument();
  });

  it("renders action_needed label", () => {
    render(
      <AllProviders>
        <SystemStatusCard level="action_needed" issueCount={1} />
      </AllProviders>,
    );
    expect(screen.getByText("Action needed")).toBeInTheDocument();
    expect(screen.getByText("1 issue detected")).toBeInTheDocument();
  });

  it("renders starting label", () => {
    render(
      <AllProviders>
        <SystemStatusCard level="starting" issueCount={0} />
      </AllProviders>,
    );
    expect(screen.getByText("Starting up")).toBeInTheDocument();
  });

  it("renders unknown label for unknown level", () => {
    render(
      <AllProviders>
        <SystemStatusCard level="unknown" issueCount={0} />
      </AllProviders>,
    );
    expect(screen.getByText("Status unknown")).toBeInTheDocument();
  });

  it("renders notes under healthy label when provided", () => {
    render(
      <AllProviders>
        <SystemStatusCard
          level="healthy"
          issueCount={0}
          notes={[
            "1 degraded data provider",
            "2 stale workers — cleaning up automatically",
          ]}
        />
      </AllProviders>,
    );
    expect(screen.getByText("All systems healthy")).toBeInTheDocument();
    expect(screen.getByText("1 degraded data provider")).toBeInTheDocument();
    expect(
      screen.getByText("2 stale workers — cleaning up automatically"),
    ).toBeInTheDocument();
  });
});
