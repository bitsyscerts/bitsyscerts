import {
  useColorSchemeContext,
  type ColorSchemeValue,
} from "@/context/ColorSchemeContext";

const CYCLE: ColorSchemeValue[] = ["system", "light", "dark"];

/**
 * Exposes the current color scheme and a cycleScheme action that advances
 * system → light → dark → system on each call.
 */
export function useColorScheme() {
  const { colorScheme, setColorScheme } = useColorSchemeContext();

  function cycleScheme() {
    const next = CYCLE[(CYCLE.indexOf(colorScheme) + 1) % CYCLE.length];
    setColorScheme(next);
  }

  return { colorScheme, cycleScheme };
}
