import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Empty = same-origin; frontend and backend served together, no hardcoded host.
  // Use a dedicated Vite-prefixed key so unrelated shell BASE_URL values don't leak into the build.
  const apiBaseUrl = env.VITE_API_BASE_URL ?? "";
  const staticAssetStamp = String(Date.now());

  return {
    define: {
      VITE_API_BASE_URL: JSON.stringify(apiBaseUrl),
      TOKEN: JSON.stringify(env.TOKEN || ""),
      MOBILE: false,
      // Bust browser cache for root-level static assets (e.g. /dark-logo.png) after each build.
      __MILU_STATIC_ASSET_STAMP__: JSON.stringify(staticAssetStamp),
    },
    plugins: [
      react(),
      {
        name: "milu-html-favicon-cache-bust",
        transformIndexHtml(html: string) {
          return html.replace(
            /href="\/milu-favicon\.png"/,
            `href="/milu-favicon.png?v=${staticAssetStamp}"`,
          );
        },
      },
    ],
    css: {
      modules: {
        localsConvention: "camelCase",
        generateScopedName: "[name]__[local]__[hash:base64:5]",
      },
      preprocessorOptions: {
        less: {
          javascriptEnabled: true,
        },
      },
    },
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
      // Dev: VITE_API_BASE_URL defaults empty → same-origin /api/*; proxy to MiLu app.
      // Override backend: console/.env.development → VITE_DEV_PROXY_TARGET=http://127.0.0.1:9090
      proxy: {
        "/api": {
          target: env.VITE_DEV_PROXY_TARGET || "http://127.0.0.1:8088",
          changeOrigin: true,
        },
      },
    },
    // build: {
    //   // Output to MiLu's console directory,
    //   // so we don't need to copy files manually after build.
    //   outDir: path.resolve(__dirname, "../src/copaw/console"),
    //   emptyOutDir: true,
    // },
  };
});
