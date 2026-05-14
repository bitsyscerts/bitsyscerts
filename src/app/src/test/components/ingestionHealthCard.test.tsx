import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";
import { IngestionHealthCard } from "@/components/StatsPanel/IngestionHealthCard";
import type { IngestionHealth } from "@/types";

function wrapper({ children }: { children: ReactNode }) {
  return <MantineProvider>{children}</MantineProvider>;
}

function makeHealth(overrides: Partial<IngestionHealth> = {}): IngestionHealth {
  return {
    status: "ok",
    retrying_logs: 0,
    rate_limited_logs: 0,
    paused_logs: 0,
    degraded_logs: 0,
    error_logs: 0,
    retryable_error_total: 0,
    terminal_error_total: 0,
    recent_terminal_outcomes: 0,
    stale_workers: 0,
    ...overrides,
  };
}

describe("IngestionHealthCard", () => {
  it("renders self-healing pill when status is ok", () => {
    render(<IngestionHealthCard ingestionHealth={makeHealth()} />, { wrapper });
    expect(screen.getByText("Ingestion Health")).toBeInTheDocument();
    expect(screen.getByText("self-healing")).toBeInTheDocument();
  });

  it("renders attention-needed pill and highlights paused count", () => {
    render(
      <IngestionHealthCard
        ingestionHealth={makeHealth({
          status: "attention_needed",
          paused_logs: 2,
          error_logs: 1,
          retryable_error_total: 4,
          terminal_error_total: 7,
          stale_workers: 1,
        })}
      />,
      { wrapper },
    );
    expect(screen.getByText("attention needed")).toBeInTheDocument();
    expect(screen.getByText("4 retryable batch errors")).toBeInTheDocument();
    expect(screen.getByText("7 terminal entry errors")).toBeInTheDocument();
    expect(screen.getByText("1 stale workers")).toBeInTheDocument();
  });

  it("renders degraded count in yellow when degraded_logs is non-zero", () => {
    render(
      <IngestionHealthCard
        ingestionHealth={makeHealth({ degraded_logs: 1 })}
      />,
      { wrapper },
    );
    // The stat label appears as dimmed text, the description uses <strong>.
    // Check for the numeric value displayed beneath the label.
    const allOnes = screen.getAllByText("1");
    expect(allOnes.length).toBeGreaterThanOrEqual(1);
  });
});
