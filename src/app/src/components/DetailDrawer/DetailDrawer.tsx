import { Box, Drawer, ScrollArea } from "@mantine/core";
import { IconCertificate, IconServer } from "@tabler/icons-react";
import { useMediaQuery } from "@mantine/hooks";
import { useState, useEffect } from "react";
import type { DrawerItem } from "@/hooks/useDrawerState";
import { truncateFingerprint } from "@/utils/format";
import { DrawerHeader } from "./DrawerHeader";
import { DrawerFooter } from "./DrawerFooter";
import { HostnameDetailBody } from "./HostnameDetailBody";
import { CertDetailBody } from "./CertDetailBody";
import { CertLookupBody } from "./CertLookupBody";

interface DetailDrawerProps {
  isOpen: boolean;
  item: DrawerItem | null;
  onClose: () => void;
}

function resolveHeader(item: DrawerItem, resolvedCn: string | null) {
  if (item.type === "hostname") {
    return {
      icon: <IconServer size={20} />,
      title: item.data.hostname,
      description: item.data.registrable_domain,
    };
  }
  if (item.type === "cert-lookup") {
    return {
      icon: <IconCertificate size={20} />,
      title: "Certificate",
      description: resolvedCn ?? truncateFingerprint(item.fingerprint),
    };
  }
  return {
    icon: <IconCertificate size={20} />,
    title: item.data.subject_common_name ?? item.data.subject_dn,
    description: item.data.fingerprint_sha256,
  };
}

/**
 * Mantine Drawer composing DrawerHeader + scrollable body + DrawerFooter.
 * Renders the correct detail body based on the discriminated-union item type.
 * Uses full-width on mobile, xl size on desktop.
 */
export function DetailDrawer({ isOpen, item, onClose }: DetailDrawerProps) {
  const isMobile = useMediaQuery("(max-width: 768px)");
  const drawerSize = isMobile ? "100%" : "xl";
  const [resolvedCn, setResolvedCn] = useState<string | null>(null);

  // Reset resolved CN whenever the drawer opens on a different item.
  const fingerprint = item?.type === "cert-lookup" ? item.fingerprint : null;
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setResolvedCn(null);
  }, [fingerprint]);
  return (
    <Drawer
      opened={isOpen}
      onClose={onClose}
      position="right"
      size={drawerSize}
      withCloseButton={false}
      styles={{
        body: {
          padding: 0,
          display: "flex",
          flexDirection: "column",
          height: "100%",
        },
      }}
    >
      {item && (
        <>
          <DrawerHeader {...resolveHeader(item, resolvedCn)} />
          <ScrollArea style={{ flex: 1 }}>
            <Box>
              {item.type === "hostname" && (
                <HostnameDetailBody item={item.data} />
              )}
              {item.type === "certificate" && (
                <CertDetailBody cert={item.data} />
              )}
              {item.type === "cert-lookup" && (
                <CertLookupBody
                  fingerprint={item.fingerprint}
                  onCnResolved={setResolvedCn}
                />
              )}
            </Box>
          </ScrollArea>
          <DrawerFooter onBack={onClose} />
        </>
      )}
    </Drawer>
  );
}
