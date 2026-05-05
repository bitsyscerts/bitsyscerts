import { useState } from "react";
import type { CertificateResponse, HostnameResult } from "@/types";

interface HostnameDrawerItem {
  type: "hostname";
  data: HostnameResult;
}

interface CertificateDrawerItem {
  type: "certificate";
  data: CertificateResponse;
}

/** Opens the drawer in fetch-on-open mode using only the fingerprint. */
interface CertLookupDrawerItem {
  type: "cert-lookup";
  fingerprint: string;
}

export type DrawerItem =
  | HostnameDrawerItem
  | CertificateDrawerItem
  | CertLookupDrawerItem;

export interface DrawerState {
  isOpen: boolean;
  item: DrawerItem | null;
  openWith: (item: DrawerItem) => void;
  close: () => void;
}

/**
 * Owns drawer open/closed state and the currently selected item as a
 * discriminated union so the drawer body knows which component to render.
 */
export function useDrawerState(): DrawerState {
  const [isOpen, setIsOpen] = useState(false);
  const [item, setItem] = useState<DrawerItem | null>(null);

  function openWith(newItem: DrawerItem) {
    setItem(newItem);
    setIsOpen(true);
  }

  function close() {
    setIsOpen(false);
    setItem(null);
  }

  return { isOpen, item, openWith, close };
}
