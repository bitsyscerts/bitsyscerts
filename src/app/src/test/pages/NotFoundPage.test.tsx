import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NotFoundPage } from "@/pages/NotFoundPage/NotFoundPage";
import { AllProviders } from "../AllProviders";

function renderPage() {
  return render(
    <AllProviders>
      <NotFoundPage />
    </AllProviders>,
  );
}

describe("NotFoundPage", () => {
  it("renders the 404 title", () => {
    renderPage();
    expect(screen.getByText("404")).toBeInTheDocument();
  });

  it("renders the page not found heading", () => {
    renderPage();
    expect(screen.getByText("Page not found")).toBeInTheDocument();
  });

  it("renders back to hosts button", () => {
    renderPage();
    expect(
      screen.getByRole("button", { name: /back to hosts/i }),
    ).toBeInTheDocument();
  });

  it("back to hosts button is clickable", () => {
    renderPage();
    const button = screen.getByRole("button", { name: /back to hosts/i });
    // Just verify the button is interactive (navigation is router-level, tested e2e)
    expect(button).not.toBeDisabled();
  });
});
