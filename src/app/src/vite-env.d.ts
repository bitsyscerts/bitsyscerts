/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** BitsysCerts build version injected at Docker build time. */
  readonly VITE_APP_VERSION: string;
  /** Dev-mode equivalents of the runtime BANNER_* vars (VITE_ prefix required by Vite). */
  readonly VITE_BANNER_VISIBLE?: string;
  readonly VITE_BANNER_TEXT?: string;
  readonly VITE_BANNER_ICON?: string;
  readonly VITE_BANNER_SEVERITY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** Runtime environment injected by docker-entrypoint.sh into env-config.js. */
interface Window {
  __ENV__?: Partial<{
    BANNER_VISIBLE: string;
    BANNER_TEXT: string;
    BANNER_SEVERITY: string;
    BANNER_ICON: string;
  }>;
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
