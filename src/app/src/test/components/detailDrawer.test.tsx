import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { IconServer } from "@tabler/icons-react";
import type { ReactNode } from "react";
import type { CertificateResponse, HostnameResult } from "@/types";
import { DrawerHeader } from "@/components/DetailDrawer/DrawerHeader";
import { DrawerFooter } from "@/components/DetailDrawer/DrawerFooter";
import { DetailField } from "@/components/DetailDrawer/DetailField";
import { HostnameDetailBody } from "@/components/DetailDrawer/HostnameDetailBody";
import { CertDetailBody } from "@/components/DetailDrawer/CertDetailBody";
import { SanList } from "@/components/DetailDrawer/SanList";

function wrapper({ children }: { children: ReactNode }) {
  return <MantineProvider>{children}</MantineProvider>;
}

const MOCK_HOSTNAME: HostnameResult = {
  id: "1",
  hostname: "sub.example.com",
  registrable_domain: "example.com",
  is_wildcard: false,
  first_seen_ct: "2023-01-01T00:00:00Z",
  last_seen_ct: "2023-06-01T00:00:00Z",
  latest_cert_not_before: "2023-01-01T00:00:00Z",
  latest_cert_not_after: "2024-01-01T00:00:00Z",
  latest_cert: null,
};

const MOCK_CERT: CertificateResponse = {
  id: "cert-1",
  fingerprint_sha256: "ab".repeat(32),
  spki_sha256: "cd".repeat(32),
  serial_number: "deadbeef",
  issuer_dn: "CN=Test CA",
  issuer_common_name: "Test CA",
  issuer_organization: "Test Org",
  subject_dn: "CN=example.com",
  subject_common_name: "example.com",
  not_before: "2023-01-01T00:00:00Z",
  not_after: "2024-01-01T00:00:00Z",
  signature_algorithm_oid: "1.2.840.113549.1.1.11",
  signature_algorithm_name: "sha256WithRSAEncryption",
  public_key_algorithm_oid: "1.2.840.113549.1.1.1",
  public_key_algorithm_name: "rsaEncryption",
  public_key_bits_or_curve: "2048",
  is_precertificate: false,
  is_wildcard_present: false,
  san_count: 2,
  first_seen_ct: "2023-01-01T00:00:00Z",
  last_seen_ct: "2023-06-01T00:00:00Z",
  subject_alternative_names: ["example.com", "www.example.com"],
};

describe("DrawerHeader", () => {
  it("renders title and description", () => {
    render(
      <DrawerHeader
        icon={<IconServer size={20} />}
        title="My Title"
        description="My Description"
      />,
      { wrapper },
    );
    expect(screen.getByText("My Title")).toBeInTheDocument();
    expect(screen.getByText("My Description")).toBeInTheDocument();
  });
});

describe("DrawerFooter", () => {
  it("renders Back button", () => {
    render(<DrawerFooter onBack={vi.fn()} />, { wrapper });
    expect(screen.getByRole("button", { name: /back/i })).toBeInTheDocument();
  });

  it("calls onBack when Back is clicked", () => {
    const onBack = vi.fn();
    render(<DrawerFooter onBack={onBack} />, { wrapper });
    screen.getByRole("button", { name: /back/i }).click();
    expect(onBack).toHaveBeenCalledOnce();
  });
});

describe("DetailField", () => {
  it("renders label and value", () => {
    render(<DetailField label="Hostname" value="example.com" />, { wrapper });
    expect(screen.getByText("Hostname")).toBeInTheDocument();
    expect(screen.getByText("example.com")).toBeInTheDocument();
  });

  it("renders dash when value is null", () => {
    render(<DetailField label="Subject CN" value={null} />, { wrapper });
    expect(screen.getByText("Subject CN")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders in monospace when mono=true", () => {
    const { container } = render(
      <DetailField label="Fingerprint" value="abc123" mono />,
      { wrapper },
    );
    expect(container).toBeTruthy();
  });
});

describe("HostnameDetailBody", () => {
  it("renders hostname field", () => {
    render(<HostnameDetailBody item={MOCK_HOSTNAME} />, { wrapper });
    expect(screen.getByText("sub.example.com")).toBeInTheDocument();
  });

  it("renders wildcard badge for wildcard hostname", () => {
    const wildcard: HostnameResult = { ...MOCK_HOSTNAME, is_wildcard: true };
    render(<HostnameDetailBody item={wildcard} />, { wrapper });
    expect(screen.getByText("Wildcard")).toBeInTheDocument();
  });

  it("renders registrable domain", () => {
    render(<HostnameDetailBody item={MOCK_HOSTNAME} />, { wrapper });
    expect(screen.getByText("example.com")).toBeInTheDocument();
  });
});

describe("CertDetailBody", () => {
  it("renders subject common name", () => {
    render(<CertDetailBody cert={MOCK_CERT} />, { wrapper });
    // subject_common_name appears at least once
    expect(screen.getAllByText("example.com").length).toBeGreaterThan(0);
  });

  it("renders issuer info", () => {
    render(<CertDetailBody cert={MOCK_CERT} />, { wrapper });
    expect(screen.getAllByText("Test CA").length).toBeGreaterThan(0);
  });

  it("renders wildcard badge when is_wildcard_present", () => {
    const cert: CertificateResponse = {
      ...MOCK_CERT,
      is_wildcard_present: true,
    };
    render(<CertDetailBody cert={cert} />, { wrapper });
    expect(screen.getByText("Wildcard")).toBeInTheDocument();
  });

  it("renders pre-certificate badge when is_precertificate", () => {
    const cert: CertificateResponse = { ...MOCK_CERT, is_precertificate: true };
    render(<CertDetailBody cert={cert} />, { wrapper });
    expect(screen.getByText("Pre-certificate")).toBeInTheDocument();
  });

  it("renders subject alternative names section", () => {
    render(<CertDetailBody cert={MOCK_CERT} />, { wrapper });
    expect(
      screen.getAllByText(/Subject Alternative Names/).length,
    ).toBeGreaterThan(0);
  });
});

describe("SanList", () => {
  it("renders SANs as badges", () => {
    render(<SanList sans={["example.com", "www.example.com"]} />, { wrapper });
    expect(screen.getByText("example.com")).toBeInTheDocument();
    expect(screen.getByText("www.example.com")).toBeInTheDocument();
  });

  it("shows placeholder when SANs is empty", () => {
    render(<SanList sans={[]} />, { wrapper });
    expect(screen.getByText(/no sans recorded/i)).toBeInTheDocument();
  });

  it("shows count in header", () => {
    render(<SanList sans={["a.com", "b.com"]} />, { wrapper });
    expect(
      screen.getByText(/Subject Alternative Names \(2\)/),
    ).toBeInTheDocument();
  });
});
