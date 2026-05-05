import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type ColorSchemeValue = "system" | "light" | "dark";

const STORAGE_KEY = "bitsyscerts-color-scheme";

interface ColorSchemeContextValue {
  colorScheme: ColorSchemeValue;
  setColorScheme: (value: ColorSchemeValue) => void;
}

const ColorSchemeContext = createContext<ColorSchemeContextValue | null>(null);

function readStoredScheme(): ColorSchemeValue {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // localStorage unavailable — fall through to default
  }
  return "system";
}

interface ColorSchemeProviderProps {
  children: ReactNode;
}

export function ColorSchemeProvider({ children }: ColorSchemeProviderProps) {
  const [colorScheme, setColorSchemeState] =
    useState<ColorSchemeValue>(readStoredScheme);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, colorScheme);
    } catch {
      // localStorage unavailable — ignore
    }
  }, [colorScheme]);

  function setColorScheme(value: ColorSchemeValue) {
    setColorSchemeState(value);
  }

  return (
    <ColorSchemeContext.Provider value={{ colorScheme, setColorScheme }}>
      {children}
    </ColorSchemeContext.Provider>
  );
}

export function useColorSchemeContext(): ColorSchemeContextValue {
  const ctx = useContext(ColorSchemeContext);
  if (!ctx) {
    throw new Error(
      "useColorSchemeContext must be used inside ColorSchemeProvider",
    );
  }
  return ctx;
}
