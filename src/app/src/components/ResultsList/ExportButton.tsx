import { Button, Menu } from "@mantine/core";
import {
  IconDownload,
  IconFileTypeCsv,
  IconFileTypeXls,
  IconJson,
} from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import type { HostnameResult } from "@/types";
import {
  exportToCSV,
  exportToJSON,
  exportToXLSX,
} from "@/services/exportService";

interface ExportButtonProps {
  items: HostnameResult[];
}

/**
 * Dropdown button (top-right of results) offering JSON, CSV, and XLSX export.
 * Disabled when the result set is empty.
 */
export function ExportButton({ items }: ExportButtonProps) {
  const disabled = items.length === 0;

  async function handleXLSX() {
    try {
      await exportToXLSX(items);
    } catch {
      notifications.show({
        title: "Export failed",
        message: "Could not generate XLSX file.",
        color: "red",
      });
    }
  }

  return (
    <Menu shadow="md" width={160} position="bottom-end">
      <Menu.Target>
        <Button
          variant="light"
          size="xs"
          leftSection={<IconDownload size={14} />}
          disabled={disabled}
        >
          Export
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>Download as</Menu.Label>
        <Menu.Item
          leftSection={<IconJson size={14} />}
          onClick={() => {
            exportToJSON(items);
          }}
        >
          JSON
        </Menu.Item>
        <Menu.Item
          leftSection={<IconFileTypeCsv size={14} />}
          onClick={() => {
            exportToCSV(items);
          }}
        >
          CSV
        </Menu.Item>
        <Menu.Item
          leftSection={<IconFileTypeXls size={14} />}
          onClick={() => void handleXLSX()}
        >
          XLSX
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}
