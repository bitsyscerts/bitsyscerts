import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { CertificatesPage } from "@/pages/CertificatesPage/CertificatesPage";
import { AllProviders } from "../AllProviders";

vi.mock("@/hooks/useCertificate", () => ({
  useCertificate: vi.fn().mockReturnValue({ data: undefined, isLoading: false, isError: false }),
}));

function renderPage() {
  return render(<AllProviders initialEntries={["/certificates"]}><CertificatesPage /></AllProviders>);
}

describe("CertificatesPage", () => {
  it("renders fingerprint input", () => {
    renderPage();
    expect(screen.getByLabelText(/sha-256 certificate fingerprint/i)).toBeInTheDocument();
  });

  it("renders look up button", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /look up/i })).toBeInTheDocument();
  });

  it("look up button is disabled when input is empty", () => {
    renderPage();
    const btn = screen.getByRole("button", { name: /look up/i });
    expect(btn).toBeDisabled();
  });
});
