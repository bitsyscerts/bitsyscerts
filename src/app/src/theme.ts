import { createTheme, type MantineColorsTuple } from "@mantine/core";

const brand: MantineColorsTuple = [
  "#f5fce6",
  "#eaf8cc",
  "#d3f09b",
  "#b8e663",
  "#a0dc35",
  "#93d213",
  "#88c402",
  "#75aa02",
  "#638f02",
  "#507201",
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
