/** Shared formatting utilities for dates, fingerprints, and numbers. */

const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  year: "numeric",
  month: "short",
  day: "2-digit",
});

const NUMBER_FORMAT = new Intl.NumberFormat("en-US");
const COMPACT_NUMBER_FORMAT = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const SIZE_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"] as const;

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return DATE_FORMAT.format(new Date(iso));
  } catch {
    return iso;
  }
}

export function truncateFingerprint(hex: string, chars = 16): string {
  return `${hex.slice(0, chars)}…`;
}

export function formatNumber(n: number): string {
  return NUMBER_FORMAT.format(n);
}

export function formatCompactNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return COMPACT_NUMBER_FORMAT.format(value);
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}

export function formatRatioPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value > 0 && value < 0.001) return "<0.1%";
  return `${(value * 100).toFixed(1)}%`;
}

export function formatStorageSize(bytes: number | null | undefined): string {
  if (
    bytes === null ||
    bytes === undefined ||
    Number.isNaN(bytes) ||
    bytes < 0
  ) {
    return "—";
  }

  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < SIZE_UNITS.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  const decimals = unitIndex >= 4 ? 2 : unitIndex >= 1 ? 1 : 0;
  return `${value.toFixed(decimals)} ${SIZE_UNITS[unitIndex]}`;
}

export function formatObservationDensity(
  bytesPerObservation: number | null | undefined,
): string {
  if (
    bytesPerObservation === null ||
    bytesPerObservation === undefined ||
    Number.isNaN(bytesPerObservation)
  ) {
    return "—";
  }
  return `${formatStorageSize(bytesPerObservation)} / observation`;
}

export function isCertExpired(notAfterIso: string | null | undefined): boolean {
  if (!notAfterIso) return false;
  return new Date(notAfterIso) < new Date();
}
