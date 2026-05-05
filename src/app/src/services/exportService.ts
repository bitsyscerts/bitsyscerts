import type { HostnameResult } from "@/types";

type ExportRow = Record<string, string | number | boolean | null>;

function flattenHostnameResult(item: HostnameResult): ExportRow {
  return {
    hostname: item.hostname,
    registrable_domain: item.registrable_domain,
    is_wildcard: item.is_wildcard,
    first_seen_ct: item.first_seen_ct ?? "",
    last_seen_ct: item.last_seen_ct ?? "",
    latest_cert_not_before: item.latest_cert_not_before ?? "",
    latest_cert_not_after: item.latest_cert_not_after ?? "",
    cert_fingerprint: item.latest_cert?.fingerprint_sha256 ?? "",
    cert_issuer:
      item.latest_cert?.issuer_common_name ?? item.latest_cert?.issuer_dn ?? "",
    cert_subject_cn: item.latest_cert?.subject_common_name ?? "",
    cert_is_precertificate: item.latest_cert?.is_precertificate ?? "",
  };
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function exportToJSON(items: HostnameResult[]): void {
  const data = JSON.stringify(items, null, 2);
  const blob = new Blob([data], { type: "application/json" });
  triggerDownload(blob, "bitsyscerts-results.json");
}

function rowsToCSV(rows: ExportRow[]): string {
  if (rows.length === 0) return "";
  const headers = Object.keys(rows[0]!);
  const escape = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lines = [
    headers.map(escape).join(","),
    ...rows.map((row) => headers.map((h) => escape(row[h])).join(",")),
  ];
  return lines.join("\r\n");
}

export function exportToCSV(items: HostnameResult[]): void {
  const rows = items.map(flattenHostnameResult);
  const csv = rowsToCSV(rows);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  triggerDownload(blob, "bitsyscerts-results.csv");
}

export async function exportToXLSX(items: HostnameResult[]): Promise<void> {
  const ExcelJS = await import("exceljs");
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet("Results");
  const rows = items.map(flattenHostnameResult);

  if (rows.length > 0) {
    sheet.columns = Object.keys(rows[0]!).map((key) => ({
      header: key,
      key,
      width: 24,
    }));
    for (const row of rows) {
      sheet.addRow(row);
    }
  }

  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  triggerDownload(blob, "bitsyscerts-results.xlsx");
}
