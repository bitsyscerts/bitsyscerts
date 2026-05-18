import { useState } from "react";
import {
  ActionIcon,
  Alert,
  Collapse,
  Container,
  Group,
  Paper,
  Stack,
  Text,
  Tooltip,
} from "@mantine/core";
import { IconAdjustmentsHorizontal, IconClock } from "@tabler/icons-react";
import { SearchBox } from "@/components/SearchBox/SearchBox";
import { SearchOptions } from "@/components/SearchOptions/SearchOptions";
import { ResultsList } from "@/components/ResultsList/ResultsList";
import { DetailDrawer } from "@/components/DetailDrawer/DetailDrawer";
import { useSearchStateContext } from "@/context/SearchStateContext";
import { useDrawerState } from "@/hooks/useDrawerState";
import { usePaginatedSearch } from "@/hooks/usePaginatedSearch";
import { useSearchUrlSync } from "@/hooks/useSearchUrlSync";
import { ApiTimeoutError } from "@/services/apiClient";
import type { CertEmbedResponse, HostnameResult } from "@/types";

/**
 * Hosts search page: search box with a collapsible filter panel (hidden by
 * default), paginated hostname results, and a detail drawer. API calls fire
 * only on explicit submit (Enter or search button click).
 */
export function HostsContent() {
  const search = useSearchStateContext();
  const drawer = useDrawerState();
  const [optionsOpen, setOptionsOpen] = useState(false);

  useSearchUrlSync(search);

  const pagination = usePaginatedSearch(
    search.buildParams,
    search.submittedQuery,
  );

  function handleSearch(value: string) {
    search.submitWithQuery(value);
  }

  function handleRowClick(item: HostnameResult) {
    drawer.openWith({ type: "hostname", data: item });
  }

  function handleCertClick(cert: CertEmbedResponse) {
    drawer.openWith({
      type: "cert-lookup",
      fingerprint: cert.fingerprint_sha256,
    });
  }

  return (
    <Container size="xl" py="md">
      <Stack gap="md">
        <Group
          gap="sm"
          align="flex-start"
          justify="center"
          wrap="nowrap"
          style={{ maxWidth: 700, margin: "0 auto", width: "100%" }}
        >
          <SearchBox
            value={search.query}
            onChange={search.setQuery}
            onSearch={handleSearch}
            placeholder="Search hostnames — exact, *.domain, or re:pattern"
          />
          <Tooltip
            label={optionsOpen ? "Hide filters" : "Show filters"}
            position="bottom"
            withArrow
          >
            <ActionIcon
              variant={optionsOpen ? "filled" : "light"}
              color="brand"
              size="input-md"
              radius="md"
              onClick={() => {
                setOptionsOpen((o) => !o);
              }}
              aria-label={
                optionsOpen ? "Hide search filters" : "Show search filters"
              }
            >
              <IconAdjustmentsHorizontal size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>

        <Collapse expanded={optionsOpen}>
          <Paper p="md" radius="md" withBorder>
            <SearchOptions
              recursive={search.options.recursive}
              onRecursiveChange={search.setRecursive}
              depth={search.options.depth}
              onDepthChange={search.setDepth}
              sort={search.options.sort}
              onSortChange={search.setSort}
              limit={search.options.limit}
              onLimitChange={search.setLimit}
              includeCerts={search.options.include_certs}
              onIncludeCertsChange={search.setIncludeCerts}
            />
          </Paper>
        </Collapse>

        {search.submittedQuery.trim() && pagination.isError && (
          <Alert
            icon={<IconClock size={16} />}
            color={
              pagination.error instanceof ApiTimeoutError ? "orange" : "red"
            }
            title={
              pagination.error instanceof ApiTimeoutError
                ? "Search timed out"
                : "Search error"
            }
          >
            <Text size="sm">
              {pagination.error instanceof ApiTimeoutError
                ? "Search timed out — try a more specific query."
                : "An unexpected error occurred. Please try again."}
            </Text>
          </Alert>
        )}

        {search.submittedQuery.trim() && !pagination.isError && (
          <ResultsList
            items={pagination.data?.items ?? []}
            isLoading={pagination.isLoading}
            onRowClick={handleRowClick}
            onCertClick={handleCertClick}
            currentPage={pagination.currentPage}
            knownPageCount={pagination.knownPageCount}
            estimatedPageCount={pagination.estimatedPageCount}
            totalEstimate={pagination.totalEstimate}
            isOverLimit={pagination.isOverLimit}
            onGoToPage={pagination.goToPage}
          />
        )}
      </Stack>

      <DetailDrawer
        isOpen={drawer.isOpen}
        item={drawer.item}
        onClose={drawer.close}
      />
    </Container>
  );
}
