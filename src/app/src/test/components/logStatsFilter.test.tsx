import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";
import { LogStatsFilter } from "@/components/StatsPanel/LogStatsFilter";

function wrapper({ children }: { children: ReactNode }) {
  return <MantineProvider>{children}</MantineProvider>;
}

const BASE_PROPS = {
  query: "",
  stateFilter: [],
  hideSynced: true,
  onQueryChange: vi.fn(),
  onStateFilterChange: vi.fn(),
  onHideSyncedChange: vi.fn(),
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
    expect(screen.getByLabelText(/hide synced logs/i)).toBeInTheDocument();
  });

  it("calls onHideSyncedChange when checkbox is toggled", () => {
    const onHideSyncedChange = vi.fn();
    render(
      <LogStatsFilter
        {...BASE_PROPS}
        onHideSyncedChange={onHideSyncedChange}
      />,
      {
        wrapper,
      },
    );

    screen.getByText("States").click();
    fireEvent.click(screen.getByLabelText(/hide synced logs/i));
    expect(onHideSyncedChange).toHaveBeenCalledWith(false);
  });

  it("calls onQueryChange when text is entered", () => {
    const onQueryChange = vi.fn();
    render(<LogStatsFilter {...BASE_PROPS} onQueryChange={onQueryChange} />, {
      wrapper,
    });
    const input = screen.getByPlaceholderText(/filter logs/i);
    fireEvent.change(input, { target: { value: "argon" } });
    expect(onQueryChange).toHaveBeenCalledWith("argon");
  });
});
