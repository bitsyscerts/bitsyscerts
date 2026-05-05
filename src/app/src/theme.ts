import { createTheme, type MantineColorsTuple } from "@mantine/core";

const brand: MantineColorsTuple = [
  "#fff0ec",
  "#fde0d8",
  "#f7bfb1",
  "#f19c86",
  "#ec7e61",
  "#e96a4a",
  "#e8603d",
  "#cf502f",
  "#b94628",
  "#a33a1e",
];

export const theme = createTheme({
  primaryColor: "brand",
  colors: { brand },
  fontFamily: "Inter, system-ui, -apple-system, sans-serif",
  fontFamilyMonospace: "'JetBrains Mono', 'Fira Code', ui-monospace, monospace",
  defaultRadius: "md",
  respectReducedMotion: true,
  components: {
    Drawer: {
      defaultProps: {
        position: "right",
        overlayProps: { backgroundOpacity: 0.35, blur: 2 },
      },
    },
    Badge: {
      defaultProps: { variant: "light" },
    },
  },
});
