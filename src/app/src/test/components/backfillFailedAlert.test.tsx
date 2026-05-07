import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AllProviders } from "../AllProviders";
import { BackfillFailedAlert } from "@/components/StatsPanel/BackfillFailedAlert";

describe("BackfillFailedAlert", () => {
  it("renders the title", () => {
    render(
      <AllProviders>
        <BackfillFailedAlert failedCount={3} />
      </AllProviders>,
    );
    expect(screen.getByText(/Failed backfill ranges detected/i)).toBeTruthy();
  });

  it("shows the failed count", () => {
    render(
      <AllProviders>
        <BackfillFailedAlert failedCount={5} />
      </AllProviders>,
    );
    expect(screen.getByText(/5 range\(s\)/i)).toBeTruthy();
  });

  it("mentions ctpool backfill command", () => {
    render(
      <AllProviders>
        <BackfillFailedAlert failedCount={1} />
      </AllProviders>,
    );
    expect(screen.getByText(/ctpool backfill/i)).toBeTruthy();
  });

  it("renders correctly for a single failed range", () => {
    render(
      <AllProviders>
        <BackfillFailedAlert failedCount={1} />
      </AllProviders>,
    );
    expect(screen.getByText(/1 range\(s\)/i)).toBeTruthy();
  });
});
