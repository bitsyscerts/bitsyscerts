import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MantineProvider } from "@mantine/core";
import { AuditHealthCard } from "../../components/StatsPanel/AuditHealthCard";
import type { AuditHealth } from "../../types/stats";

function renderCard(auditHealth: AuditHealth) {
  return render(
    <MantineProvider>
      <AuditHealthCard auditHealth={auditHealth} />
    </MantineProvider>,
  );
}

const cleanHealth: AuditHealth = {
  open_critical: 0,
  open_error: 0,
  open_warning: 0,
  open_info: 0,
  total_open: 0,
  status: "ok",
};

const dirtyHealth: AuditHealth = {
  open_critical: 2,
  open_error: 1,
  open_warning: 3,
  open_info: 0,
  total_open: 6,
  status: "attention_needed",
};

describe("AuditHealthCard", () => {
  it("renders clean state when total_open is zero", () => {
    renderCard(cleanHealth);
    expect(screen.getByText(/no open audit findings/i)).toBeInTheDocument();
  });

  it("does not show badges when total_open is zero", () => {
    renderCard(cleanHealth);
    expect(screen.queryByText(/critical/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
  });

  it("displays critical count when open_critical > 0", () => {
    renderCard(dirtyHealth);
    expect(screen.getByText(/2 critical/i)).toBeInTheDocument();
  });

  it("displays error count when open_error > 0", () => {
    renderCard(dirtyHealth);
    expect(screen.getByText(/1 error/i)).toBeInTheDocument();
  });

  it("displays warning count when open_warning > 0", () => {
    renderCard(dirtyHealth);
    expect(screen.getByText(/3 warning/i)).toBeInTheDocument();
  });

  it("shows severity labels for critical and error", () => {
    renderCard(dirtyHealth);
    expect(screen.getByText(/critical/i)).toBeInTheDocument();
    expect(screen.getByText(/error/i)).toBeInTheDocument();
    expect(screen.getByText(/warning/i)).toBeInTheDocument();
  });

  it("does not show info badge when open_info is zero", () => {
    renderCard(dirtyHealth);
    expect(screen.queryByText(/info/i)).not.toBeInTheDocument();
  });

  it("shows info badge when open_info > 0", () => {
    const withInfo: AuditHealth = {
      ...dirtyHealth,
      open_info: 5,
      total_open: 11,
    };
    renderCard(withInfo);
    expect(screen.getByText(/5 info/i)).toBeInTheDocument();
  });
});
