import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  formatDate,
  truncateFingerprint,
  formatNumber,
  formatPct,
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
