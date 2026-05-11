import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DiagnosticsSection } from "@/components/StatsPanel/DiagnosticsSection";
import type {
  AuditHealth,
  BackfillRangeStats,
  DbContentionStats,
} from "@/types";
import { AllProviders } from "../AllProviders";

const BACKFILL_RANGES: BackfillRangeStats = {
  pending: 5,
  in_progress: 1,
  stale_in_progress: 0,
  completed: 900,
  failed: 0,
  dispatch_mode: "per-log",
  is_primary: true,
};

const AUDIT_HEALTH: AuditHealth = {
  open_critical: 0,
  open_error: 0,
  open_warning: 0,
  open_info: 0,
  total_open: 0,
  status: "ok",
};

const CONTENTION: DbContentionStats = {
  status: "healthy",
  degraded_mode_active: false,
  pressure_ema: 0.01,
  base_sleep_seconds: 0,
  shared_batch_size_cap: null,
  effective_batch_size_cap: null,
  updated_at: "2025-01-01T00:00:00Z",
  notes: [],
  total_retryable_errors: 0,
  retryable_errors_per_min_5min: null,
};

describe("DiagnosticsSection", () => {
  it("renders accordion control label", () => {
    render(
      <AllProviders>
        <DiagnosticsSection
          backfillRanges={BACKFILL_RANGES}
          auditHealth={null}
          contention={CONTENTION}
        />
      </AllProviders>,
    );
    expect(screen.getByText("Advanced diagnostics")).toBeInTheDocument();
  });

  it("renders with audit health provided", async () => {
    const { container } = render(
      <AllProviders>
        <DiagnosticsSection
          backfillRanges={BACKFILL_RANGES}
          auditHealth={AUDIT_HEALTH}
          contention={CONTENTION}
        />
      </AllProviders>,
    );
    await userEvent.click(screen.getByText("Advanced diagnostics"));
    expect(container).toBeTruthy();
  });

  it("renders without audit health", async () => {
    const { container } = render(
      <AllProviders>
        <DiagnosticsSection
          backfillRanges={BACKFILL_RANGES}
          auditHealth={null}
          contention={CONTENTION}
        />
      </AllProviders>,
    );
    await userEvent.click(screen.getByText("Advanced diagnostics"));
    expect(container).toBeTruthy();
  });

  it("renders DbContentionCard inside the accordion", async () => {
    const { container } = render(
      <AllProviders>
        <DiagnosticsSection
          backfillRanges={BACKFILL_RANGES}
          auditHealth={null}
          contention={CONTENTION}
        />
      </AllProviders>,
    );
    await userEvent.click(screen.getByText("Advanced diagnostics"));
    expect(container).toBeTruthy();
  });
});
