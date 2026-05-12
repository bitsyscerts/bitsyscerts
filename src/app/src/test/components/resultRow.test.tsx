import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";
import type { CertEmbedResponse, HostnameResult } from "@/types";
import { HostnameResultRow } from "@/components/ResultRow/HostnameResultRow";
import { CertEmbedRow } from "@/components/ResultRow/CertEmbedRow";
import { ResultRowSkeleton } from "@/components/ResultRow/ResultRowSkeleton";

function wrapper({ children }: { children: ReactNode }) {
  return <MantineProvider>{children}</MantineProvider>;
}

const MOCK_CERT: CertEmbedResponse = {
  fingerprint_sha256: "ab".repeat(32),
  spki_sha256: "cd".repeat(32),
  not_before: "2023-01-01T00:00:00Z",
  not_after: "2024-01-01T00:00:00Z",
  issuer_dn: "CN=Test CA",
  issuer_common_name: "Test CA",
  issuer_organization: "Test Org",
  subject_common_name: "example.com",
  is_wildcard_present: false,
  is_precertificate: false,
  subject_alternative_names: [],
};

const MOCK_ITEM: HostnameResult = {
  id: "1",
  hostname: "example.com",
  registrable_domain: "example.com",
  is_wildcard: false,
  first_seen_ct: "2023-01-01T00:00:00Z",
  last_seen_ct: "2023-06-01T00:00:00Z",
  latest_cert_not_before: "2023-01-01T00:00:00Z",
  latest_cert_not_after: "2024-01-01T00:00:00Z",
  latest_cert: MOCK_CERT,
};

const WILDCARD_ITEM: HostnameResult = {
  ...MOCK_ITEM,
  id: "2",
  hostname: "*.example.com",
  is_wildcard: true,
  latest_cert: null,
};

const EXPIRED_ITEM: HostnameResult = {
  ...MOCK_ITEM,
  id: "3",
  latest_cert_not_after: "2020-01-01T00:00:00Z",
  latest_cert: null,
};

describe("HostnameResultRow", () => {
  it("renders hostname", () => {
    render(<HostnameResultRow item={MOCK_ITEM} onClick={vi.fn()} />, {
      wrapper,
    });
    // hostname appears at least once (also as registrable_domain)
    expect(screen.getAllByText("example.com").length).toBeGreaterThan(0);
  });

  it("renders wildcard badge for wildcard entry", () => {
    render(<HostnameResultRow item={WILDCARD_ITEM} onClick={vi.fn()} />, {
      wrapper,
    });
    expect(screen.getByText("wildcard")).toBeInTheDocument();
  });

  it("renders expired badge for expired cert", () => {
    render(<HostnameResultRow item={EXPIRED_ITEM} onClick={vi.fn()} />, {
      wrapper,
    });
    expect(screen.getByText("expired")).toBeInTheDocument();
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<HostnameResultRow item={MOCK_ITEM} onClick={onClick} />, {
      wrapper,
    });
    screen.getByRole("button", { name: "Open hostname example.com" }).click();
    expect(onClick).toHaveBeenCalledWith(MOCK_ITEM);
  });

  it("supports keyboard activation", () => {
    const onClick = vi.fn();
    render(<HostnameResultRow item={MOCK_ITEM} onClick={onClick} />, {
      wrapper,
    });

    fireEvent.keyDown(
      screen.getByRole("button", { name: "Open hostname example.com" }),
      { key: "Enter" },
    );

    expect(onClick).toHaveBeenCalledWith(MOCK_ITEM);
  });

  it("renders embedded cert row when latest_cert is present", () => {
    render(<HostnameResultRow item={MOCK_ITEM} onClick={vi.fn()} />, {
      wrapper,
    });
    // CertEmbedRow shows truncated fingerprint
    expect(screen.getByText(/abababab/)).toBeInTheDocument();
  });

  it("keeps the embedded cert row clickable without nested button warnings", () => {
    const onClick = vi.fn();
    const onCertClick = vi.fn();
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    render(
      <HostnameResultRow
        item={MOCK_ITEM}
        onClick={onClick}
        onCertClick={onCertClick}
      />,
      { wrapper },
    );

    screen
      .getByRole("button", { name: "Open embedded certificate details" })
      .click();

    expect(onCertClick).toHaveBeenCalledWith(MOCK_CERT);
    expect(onClick).not.toHaveBeenCalled();
    expect(
      consoleError.mock.calls.some(([message]) =>
        String(message).includes("cannot appear as a descendant of <button>"),
      ),
    ).toBe(false);

    consoleError.mockRestore();
  });
});

describe("CertEmbedRow", () => {
  it("renders fingerprint", () => {
    render(<CertEmbedRow cert={MOCK_CERT} />, { wrapper });
    expect(screen.getByText(/abababab/)).toBeInTheDocument();
  });

  it("renders issuer common name", () => {
    render(<CertEmbedRow cert={MOCK_CERT} />, { wrapper });
    expect(screen.getByText("Test CA")).toBeInTheDocument();
  });

  it("renders wildcard badge when is_wildcard_present", () => {
    const cert = { ...MOCK_CERT, is_wildcard_present: true };
    render(<CertEmbedRow cert={cert} />, { wrapper });
    expect(screen.getByText("wildcard")).toBeInTheDocument();
  });

  it("renders pre-cert badge when is_precertificate", () => {
    const cert = { ...MOCK_CERT, is_precertificate: true };
    render(<CertEmbedRow cert={cert} />, { wrapper });
    expect(screen.getByText("pre-cert")).toBeInTheDocument();
  });

  it("shows chevron icon when onClick provided", () => {
    const { container } = render(
      <CertEmbedRow cert={MOCK_CERT} onClick={vi.fn()} />,
      { wrapper },
    );
    // The chevron SVG should be present when onClick is provided
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("falls back to issuer_organization when issuer_common_name is null", () => {
    const cert: CertEmbedResponse = {
      ...MOCK_CERT,
      issuer_common_name: null,
      issuer_organization: "My Org",
    };
    render(<CertEmbedRow cert={cert} />, { wrapper });
    expect(screen.getByText("My Org")).toBeInTheDocument();
  });

  it("falls back to issuer_dn when both cn and org are null", () => {
    const cert: CertEmbedResponse = {
      ...MOCK_CERT,
      issuer_common_name: null,
      issuer_organization: null,
    };
    render(<CertEmbedRow cert={cert} />, { wrapper });
    expect(screen.getByText("CN=Test CA")).toBeInTheDocument();
  });
});

describe("ResultRowSkeleton", () => {
  it("renders without crash", () => {
    const { container } = render(<ResultRowSkeleton />, { wrapper });
    expect(container).toBeTruthy();
  });
});
