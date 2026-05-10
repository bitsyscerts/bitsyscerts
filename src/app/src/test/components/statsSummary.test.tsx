import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";
import { StatsSummary } from "@/components/StatsPanel/StatsSummary";

function wrapper({ children }: { children: ReactNode }) {
  return <MantineProvider>{children}</MantineProvider>;
}

describe("StatsSummary", () => {
  it("renders the three top-level totals", () => {
    render(
      <StatsSummary
        totalHostnames={63_755}
        totalCertificates={29_185}
        totalLogs={35}
      />,
      { wrapper },
    );

    expect(screen.getByText("Hostnames")).toBeInTheDocument();
    expect(screen.getByText("Certificates")).toBeInTheDocument();
    expect(screen.getAllByText("CT Logs").length).toBeGreaterThan(0);
    expect(screen.getByText("63,755")).toBeInTheDocument();
    expect(screen.getByText("29,185")).toBeInTheDocument();
    expect(screen.getByText("35")).toBeInTheDocument();
  });
});
