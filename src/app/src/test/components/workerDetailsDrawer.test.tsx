import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorkerDetailsDrawer } from "@/components/StatsPanel/WorkerDetailsDrawer";
import type { WorkerSummary } from "@/types";
import { AllProviders } from "../AllProviders";

const WORKERS: WorkerSummary = {
  active_total: 2,
  stale_total: 0,
  tail_active: 2,
  backfill_active: 0,
  stats_active: 0,
  maintenance_active: 0,
  unknown_active: 0,
  items: [],
};

describe("WorkerDetailsDrawer", () => {
  it("does not render drawer content when closed", () => {
    render(
      <AllProviders>
        <WorkerDetailsDrawer opened={false} onClose={vi.fn()} workers={null} />
      </AllProviders>,
    );
    expect(screen.queryByText("Worker Activity")).toBeNull();
  });

  it("renders title and description when open with no workers", () => {
    render(
      <AllProviders>
        <WorkerDetailsDrawer opened onClose={vi.fn()} workers={null} />
      </AllProviders>,
    );
    expect(screen.getByText("Worker Activity")).toBeInTheDocument();
    expect(screen.getByText(/Active ingestion workers/i)).toBeInTheDocument();
  });

  it("renders WorkerActivityCard when workers are provided", () => {
    render(
      <AllProviders>
        <WorkerDetailsDrawer opened onClose={vi.fn()} workers={WORKERS} />
      </AllProviders>,
    );
    expect(screen.getAllByText("Worker Activity").length).toBeGreaterThan(0);
  });

  it("calls onClose when close button is clicked", async () => {
    const onClose = vi.fn();
    render(
      <AllProviders>
        <WorkerDetailsDrawer opened onClose={onClose} workers={null} />
      </AllProviders>,
    );
    const backBtn = screen.getByRole("button", { name: /back/i });
    await userEvent.click(backBtn);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
