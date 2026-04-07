/// <reference types="vite/client" />

declare module "*.less" {
  const classes: { [key: string]: string };
  export default classes;
}

interface PyWebViewAPI {
  open_external_link: (url: string) => void;
}

declare global {
  /** Set by Vite `define` in vite.config.ts (build-time stamp for logo cache bust). */
  // eslint-disable-next-line no-var
  var __MILU_STATIC_ASSET_STAMP__: string;

  interface Window {
    pywebview?: {
      api: PyWebViewAPI;
    };
  }
}

export {};
