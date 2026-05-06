import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  formatDate,
  formatCompactNumber,
  formatObservationDensity,
  truncateFingerprint,
  formatNumber,
  formatPct,
  formatRatioPct,
  formatStorageSize,
  isCertExpired,
} from "@/utils/format";

describe("formatDate", () => {
  it("returns em-dash for null", () => {
    expect(formatDate(null)).toBe("—");
  });

  it("returns em-dash for undefined", () => {
    expect(formatDate(undefined)).toBe("—");
  });

  it("returns em-dash for empty string", () => {
    expect(formatDate("")).toBe("—");
  });

  it("formats a valid ISO date string", () => {
    const result = formatDate("2024-06-15T12:00:00Z");
    // en-GB format: "15 Jun 2024"
    expect(result).toMatch(/2024/);
    expect(result).toMatch(/Jun/);
    expect(result).toMatch(/15/);
  });

  it("returns the raw string when the date is unparseable", () => {
    const raw = "not-a-date";
    expect(formatDate(raw)).toBe(raw);
  });
});

describe("truncateFingerprint", () => {
  it("truncates to 16 chars by default and appends ellipsis", () => {
    const fp = "a".repeat(64);
    const result = truncateFingerprint(fp);
    expect(result).toBe(`${"a".repeat(16)}…`);
  });

  it("truncates to a custom length", () => {
    const fp = "abcdefghijklmnopqrstuvwxyz";
    expect(truncateFingerprint(fp, 4)).toBe("abcd…");
  });
});

describe("formatNumber", () => {
  it("formats zero", () => {
    expect(formatNumber(0)).toBe("0");
  });

  it("adds thousands separator", () => {
    expect(formatNumber(1_000_000)).toBe("1,000,000");
  });
});

describe("formatCompactNumber", () => {
  it("formats large values compactly", () => {
    expect(formatCompactNumber(6_300_000)).toBe("6.3M");
    expect(formatCompactNumber(4_800_000_000)).toBe("4.8B");
  });
});

describe("formatPct", () => {
  it("returns em-dash for null", () => {
    expect(formatPct(null)).toBe("—");
  });

  it("returns em-dash for undefined", () => {
    expect(formatPct(undefined)).toBe("—");
  });

  it("formats a number with one decimal place", () => {
    expect(formatPct(75)).toBe("75.0%");
    expect(formatPct(0)).toBe("0.0%");
    expect(formatPct(100)).toBe("100.0%");
    expect(formatPct(33.333)).toBe("33.3%");
  });
});

describe("formatRatioPct", () => {
  it("returns em-dash for nullish values", () => {
    expect(formatRatioPct(null)).toBe("—");
    expect(formatRatioPct(undefined)).toBe("—");
  });

  it("formats ratios as percentages", () => {
    expect(formatRatioPct(0.423)).toBe("42.3%");
    expect(formatRatioPct(0.001)).toBe("0.1%");
    expect(formatRatioPct(0.0009)).toBe("<0.1%");
  });
});

describe("formatStorageSize", () => {
  it("returns em-dash for nullish input", () => {
    expect(formatStorageSize(null)).toBe("—");
    expect(formatStorageSize(undefined)).toBe("—");
  });

  it("uses binary units and one decimal for KB/MB/GB", () => {
    expect(formatStorageSize(1024)).toBe("1.0 KB");
    expect(formatStorageSize(1024 ** 2)).toBe("1.0 MB");
    expect(formatStorageSize(1024 ** 3)).toBe("1.0 GB");
  });

  it("uses two decimals for TB and above", () => {
    const onePointThreeThreeTb = Math.round(1.33 * 1024 ** 4);
    expect(formatStorageSize(onePointThreeThreeTb)).toBe("1.33 TB");
  });
});

describe("formatObservationDensity", () => {
  it("appends the observation suffix", () => {
    expect(formatObservationDensity(1_252.44)).toBe("1.2 KB / observation");
  });
});

describe("isCertExpired", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-06-01T00:00:00Z"));
  });

  it("returns false for null", () => {
    expect(isCertExpired(null)).toBe(false);
  });

  it("returns false for undefined", () => {
    expect(isCertExpired(undefined)).toBe(false);
  });

  it("returns true when the cert has expired", () => {
    expect(isCertExpired("2023-01-01T00:00:00Z")).toBe(true);
  });

  it("returns false when the cert has not expired", () => {
    expect(isCertExpired("2025-01-01T00:00:00Z")).toBe(false);
  });
});
