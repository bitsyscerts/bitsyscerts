import { createContext, useContext, useState, type ReactNode } from "react";

export interface CertState {
  input: string;
  submittedFp: string;
  setInput: (value: string) => void;
  submitLookup: (fp: string) => void;
}

const CertStateContext = createContext<CertState | null>(null);

interface CertStateProviderProps {
  children: ReactNode;
}

/**
 * Lifts certificate lookup state above the router so the fingerprint input
 * and result survive navigation between pages.
 */
export function CertStateProvider({ children }: CertStateProviderProps) {
  const [input, setInput] = useState("");
  const [submittedFp, setSubmittedFp] = useState("");

  function submitLookup(fp: string) {
    setInput(fp);
    setSubmittedFp(fp);
  }

  return (
    <CertStateContext.Provider
      value={{ input, submittedFp, setInput, submitLookup }}
    >
      {children}
    </CertStateContext.Provider>
  );
}

export function useCertStateContext(): CertState {
  const ctx = useContext(CertStateContext);
  if (!ctx) {
    throw new Error(
      "useCertStateContext must be used inside CertStateProvider",
    );
  }
  return ctx;
}
