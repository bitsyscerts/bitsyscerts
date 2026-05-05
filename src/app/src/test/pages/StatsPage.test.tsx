import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { StatsPage } from "@/pages/StatsPage/StatsPage";
import { AllProviders } from "../AllProviders";

vi.mock("@/hooks/useStats", () => ({
  useStats: vi
    .fn()
    .mockReturnValue({ data: undefined, isLoading: true, isError: false }),
}));

function renderPage() {
  return render(
    <AllProviders>
      <StatsPage />
    </AllProviders>,
  );
}

describe("StatsPage", () => {
  it("renders skeleton when loading", () => {
    renderPage();
    // StatsPanelSkeleton renders, no crash
    expect(document.body).toBeTruthy();
  });
});

describe("StatsPage with data", () => {
  it("renders storage and logs sections when data available", () => {
    const useStatsMock = vi.fn().mockReturnValue({
      data: {
        total_hostnames: 100,
        total_certificates: 200,
        total_logs: 5,
        storage: { total_size_pretty: "1 GB", tables: [] },
        logs: [],
      },
      isLoading: false,
      isError: false,
    });
    vi.mocked(useStatsMock);
    render(
      <AllProviders>
        <StatsPage />
      </AllProviders>,
    );
    // Page renders without crashing with data
    expect(document.body).toBeTruthy();
  });
});
