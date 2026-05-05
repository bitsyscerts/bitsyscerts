import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AllProviders } from "../AllProviders";

// Mock the heavy content component to keep the test lightweight
vi.mock("@/pages/SearchPage/SearchPageContent", () => ({
  HostsContent: () => <div><input placeholder="Search hostnames" /></div>,
}));

import { HostsPage } from "@/pages/SearchPage/SearchPage";

function renderPage() {
  return render(<AllProviders><HostsPage /></AllProviders>);
}

describe("HostsPage", () => {
  it("renders wrapped content without crashing", () => {
    renderPage();
    expect(document.body).toBeTruthy();
  });

  it("renders search input", () => {
    renderPage();
    expect(screen.getByPlaceholderText("Search hostnames")).toBeInTheDocument();
  });
});
