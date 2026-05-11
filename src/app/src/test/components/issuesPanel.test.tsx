import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { IssuesPanel } from "@/components/StatsPanel/IssuesPanel";
import type { DerivedIssue } from "@/utils/deriveSystemStatus";
import { AllProviders } from "../AllProviders";

describe("IssuesPanel", () => {
  it("renders empty state when there are no issues", () => {
    render(
      <AllProviders>
        <IssuesPanel issues={[]} />
      </AllProviders>,
    );
    expect(screen.getByText("No action needed.")).toBeInTheDocument();
  });

  it("renders action_needed issues", () => {
    const issues: DerivedIssue[] = [
      { severity: "action_needed", message: "Critical disk space issue." },
    ];
    render(
      <AllProviders>
        <IssuesPanel issues={issues} />
      </AllProviders>,
    );
    expect(screen.getByText("Critical disk space issue.")).toBeInTheDocument();
    expect(screen.queryByText("No action needed.")).toBeNull();
  });

  it("renders warning issues", () => {
    const issues: DerivedIssue[] = [
      { severity: "warning", message: "2 stale CT logs." },
    ];
    render(
      <AllProviders>
        <IssuesPanel issues={issues} />
      </AllProviders>,
    );
    expect(screen.getByText("2 stale CT logs.")).toBeInTheDocument();
  });

  it("renders multiple issues of mixed severity", () => {
    const issues: DerivedIssue[] = [
      { severity: "action_needed", message: "Action needed message." },
      { severity: "warning", message: "Warning message." },
    ];
    render(
      <AllProviders>
        <IssuesPanel issues={issues} />
      </AllProviders>,
    );
    expect(screen.getByText("Action needed message.")).toBeInTheDocument();
    expect(screen.getByText("Warning message.")).toBeInTheDocument();
  });
});
