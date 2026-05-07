import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { LogStaleBadge } from "@/components/StatsPanel/LogStaleBadge";
import { AllProviders } from "../AllProviders";

describe("LogStaleBadge", () => {
  it("renders fresh badge when lag is below threshold", () => {
    render(
      <AllProviders>
        <LogStaleBadge lagSeconds={60} thresholdSeconds={300} />
      </AllProviders>,
    );
    expect(screen.getByText("fresh")).toBeInTheDocument();
  });

  it("renders stale badge with lag text when lag meets threshold", () => {
    render(
      <AllProviders>
        <LogStaleBadge lagSeconds={600} thresholdSeconds={300} />
      </AllProviders>,
    );
    expect(screen.getByText(/stale/)).toBeInTheDocument();
    expect(screen.getByText(/10m/)).toBeInTheDocument();
  });

  it("renders stale at exactly the threshold", () => {
    render(
      <AllProviders>
        <LogStaleBadge lagSeconds={300} thresholdSeconds={300} />
      </AllProviders>,
    );
    expect(screen.getByText(/stale/)).toBeInTheDocument();
  });

  it("renders nothing when lag is null", () => {
    render(
      <AllProviders>
        <div data-testid="wrapper">
          <LogStaleBadge lagSeconds={null} />
        </div>
      </AllProviders>,
    );
    expect(screen.getByTestId("wrapper")).toBeEmptyDOMElement();
  });
});
