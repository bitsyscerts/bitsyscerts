import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";
import { LogStatsFilter } from "@/components/StatsPanel/LogStatsFilter";

function wrapper({ children }: { children: ReactNode }) {
  return <MantineProvider>{children}</MantineProvider>;
}

const BASE_PROPS = {
  query: "",
  stateFilter: [],
  onQueryChange: vi.fn(),
  onStateFilterChange: vi.fn(),
  totalCount: 10,
  filteredCount: 10,
};

describe("LogStatsFilter", () => {
  it("renders filter input", () => {
    render(<LogStatsFilter {...BASE_PROPS} />, { wrapper });
    expect(screen.getByPlaceholderText(/filter logs/i)).toBeInTheDocument();
  });

  it("shows total count when not filtered", () => {
    render(<LogStatsFilter {...BASE_PROPS} />, { wrapper });
    expect(screen.getByText("10")).toBeInTheDocument();
  });

  it("shows filtered/total when filtered", () => {
    render(
      <LogStatsFilter {...BASE_PROPS} filteredCount={3} totalCount={10} />,
      { wrapper },
    );
    expect(screen.getByText("3 / 10")).toBeInTheDocument();
  });

  it("shows state chips when filter panel is opened", () => {
    render(<LogStatsFilter {...BASE_PROPS} />, { wrapper });
    const statesBtn = screen.getByText("States");
    statesBtn.click();
    expect(screen.getByText("Usable")).toBeInTheDocument();
    expect(screen.getByText("Readonly")).toBeInTheDocument();
    expect(screen.getByText("Retired")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("calls onQueryChange when text is entered", () => {
    const onQueryChange = vi.fn();
    render(<LogStatsFilter {...BASE_PROPS} onQueryChange={onQueryChange} />, {
      wrapper,
    });
    const input = screen.getByPlaceholderText(/filter logs/i);
    Object.defineProperty(input, "value", { value: "argon" });
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
});
