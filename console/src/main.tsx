import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./i18n";

/** Tab favicon: absolute URL + build stamp (survives cached HTML / odd webviews). */
function ensureMiluFavicon() {
  if (typeof window === "undefined") return;
  const stamp = __MILU_STATIC_ASSET_STAMP__;
  // BASE_URL 可能是相对（"./"）或绝对（"/console/"）：以当前文档为基准解析，
  // 避免 origin + BASE_URL 直接拼接产生非法 base（子路径部署下会抛 Invalid base URL）
  const originBase = new URL(import.meta.env.BASE_URL || "/", document.baseURI).href;
  const href = new URL(
    `logo.png?v=${encodeURIComponent(stamp)}`,
    originBase.endsWith("/") ? originBase : `${originBase}/`,
  ).href;

  document
    .querySelectorAll('link[rel="icon"], link[rel="shortcut icon"]')
    .forEach((el) => el.remove());

  const link = document.createElement("link");
  link.rel = "icon";
  link.type = "image/png";
  link.href = href;
  document.head.prepend(link);
}

ensureMiluFavicon();

if (typeof window !== "undefined") {
  const originalError = console.error;
  const originalWarn = console.warn;

  console.error = function (...args: any[]) {
    const msg = args[0]?.toString() || "";
    if (msg.includes(":first-child") || msg.includes("pseudo class")) {
      return;
    }
    originalError.apply(console, args);
  };

  console.warn = function (...args: any[]) {
    const msg = args[0]?.toString() || "";
    if (
      msg.includes(":first-child") ||
      msg.includes("pseudo class") ||
      msg.includes("potentially unsafe")
    ) {
      return;
    }
    originalWarn.apply(console, args);
  };
}

createRoot(document.getElementById("root")!).render(<App />);
