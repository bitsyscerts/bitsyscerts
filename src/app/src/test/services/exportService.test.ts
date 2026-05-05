import { describe, it, expect, vi, beforeEach } from "vitest";
import { exportToJSON, exportToCSV } from "@/services/exportService";
import type { HostnameResult } from "@/types";

// ── Browser API mocks ──────────────────────────────────────────────────────
const mockClick = vi.fn();
const mockCreateObjectURL = vi.fn(() => "blob:mock-url");
const mockRevokeObjectURL = vi.fn();

beforeEach(() => {
  mockClick.mockReset();
  mockCreateObjectURL.mockReturnValue("blob:mock-url");

  vi.stubGlobal("URL", {
    createObjectURL: mockCreateObjectURL,
    revokeObjectURL: mockRevokeObjectURL,
  });

  // Minimal anchor stub
  vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
    if (tag === "a") {
      return {
        href: "",
        download: "",
        click: mockClick,
      } as unknown as HTMLAnchorElement;
    }
    return document.createElement(tag);
  });
});

const ITEM: HostnameResult = {
  id: "item-1",
  hostname: "test.example.com",
  registrable_domain: "example.com",
  is_wildcard: false,
  first_seen_ct: "2024-01-01T00:00:00Z",
  last_seen_ct: "2024-06-01T00:00:00Z",
  latest_cert_not_before: "2024-01-01T00:00:00Z",
  latest_cert_not_after: "2025-01-01T00:00:00Z",
  latest_cert: null,
};

describe("exportToJSON", () => {
  it("triggers a download without throwing", () => {
    expect(() => {
      exportToJSON([ITEM]);
    }).not.toThrow();
    expect(mockCreateObjectURL).toHaveBeenCalled();
    expect(mockClick).toHaveBeenCalled();
  });

  it("does not throw for an empty array", () => {
    expect(() => {
      exportToJSON([]);
    }).not.toThrow();
  });
});

describe("exportToCSV", () => {
  it("triggers a download without throwing", () => {
    expect(() => {
      exportToCSV([ITEM]);
    }).not.toThrow();
    expect(mockCreateObjectURL).toHaveBeenCalled();
    expect(mockClick).toHaveBeenCalled();
  });

  it("does not throw for an empty array", () => {
    expect(() => {
      exportToCSV([]);
    }).not.toThrow();
  });
});
