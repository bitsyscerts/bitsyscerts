import { ScrollArea, Table, Text } from "@mantine/core";
import type { TableStorageItem } from "@/types";
import { formatNumber, formatStorageSize } from "@/utils/format";

interface StorageTableProps {
  tables: TableStorageItem[];
  totalSizeBytes: number;
}

/**
 * Table of database storage usage by table name, row estimate, and size.
 */
export function StorageTable({ tables, totalSizeBytes }: StorageTableProps) {
  return (
    <ScrollArea>
      <Table
        striped
        highlightOnHover
        withTableBorder
        withColumnBorders
        fz="xs"
        miw={520}
      >
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Table</Table.Th>
            <Table.Th ta="right">Rows (est.)</Table.Th>
            <Table.Th ta="right">Size</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {tables.map((row) => (
            <Table.Tr key={row.table_name}>
              <Table.Td ff="monospace">{row.table_name}</Table.Td>
              <Table.Td ta="right">{formatNumber(row.row_estimate)}</Table.Td>
              <Table.Td ta="right">
                {formatStorageSize(row.size_bytes)}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
        <Table.Tfoot>
          <Table.Tr>
            <Table.Td colSpan={2}>
              <Text size="xs" fw={600}>
                Total
              </Text>
            </Table.Td>
            <Table.Td ta="right">
              <Text size="xs" fw={600}>
                {formatStorageSize(totalSizeBytes)}
              </Text>
            </Table.Td>
          </Table.Tr>
        </Table.Tfoot>
      </Table>
    </ScrollArea>
  );
}
