/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** BitsysCerts build version injected at Docker build time. */
  readonly VITE_APP_VERSION: string;
  /** Set to "true" to show the announcement banner on the dashboard. */
  readonly VITE_BANNER_VISIBLE?: string;
  /** Text displayed inside the announcement banner. */
  readonly VITE_BANNER_TEXT?: string;
  /**
   * Tabler icon name (without the "Icon" prefix) for the banner.
   * Supported: InfoCircle (default), AlertTriangle, AlertCircle,
   * CircleCheck, Speakerphone.
   */
  readonly VITE_BANNER_ICON?: string;
  /**
   * Mantine Alert color for the banner.
   * Supported: info (default) | warning | error | success.
   */
  readonly VITE_BANNER_SEVERITY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.png" {
  const src: string;
  export default src;
}
declare module "*.svg" {
  const src: string;
  export default src;
}
declare module "*.jpg" {
  const src: string;
  export default src;
}
