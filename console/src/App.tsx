import { createGlobalStyle } from "antd-style";
import { ConfigProvider, bailianTheme } from "@agentscope-ai/design";
import { App as AntdApp } from "antd";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import zhCN from "antd/locale/zh_CN";
import enUS from "antd/locale/en_US";
import jaJP from "antd/locale/ja_JP";
import ruRU from "antd/locale/ru_RU";
import type { Locale } from "antd/es/locale";
import { theme as antdTheme } from "antd";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/zh-cn";
import "dayjs/locale/ja";
import "dayjs/locale/ru";
dayjs.extend(relativeTime);
import MainLayout from "./layouts/MainLayout";
import { ThemeProvider, useTheme } from "./contexts/ThemeContext";
import LoginPage from "./pages/Login";
import { authApi } from "./api/modules/auth";
import { languageApi } from "./api/modules/language";
import { getApiUrl, getApiToken, clearAuthToken } from "./api/config";
import { MILU_BRAND } from "./constants/brandColors";
import "./styles/layout.css";
import "./styles/form-override.css";

const antdLocaleMap: Record<string, Locale> = {
  zh: zhCN,
  en: enUS,
  ja: jaJP,
  ru: ruRU,
};

const dayjsLocaleMap: Record<string, string> = {
  zh: "zh-cn",
  en: "en",
  ja: "ja",
  ru: "ru",
};

const GlobalStyle = createGlobalStyle`
:root {
  --milu-primary: ${MILU_BRAND.primary};
  --milu-primary-rgb: ${MILU_BRAND.primaryRgb};
  --milu-accent: ${MILU_BRAND.accent};
  --milu-accent-rgb: ${MILU_BRAND.accentRgb};
  --milu-navy: ${MILU_BRAND.navy};
  --milu-navy-rgb: ${MILU_BRAND.navyRgb};
  --milu-page-bg: ${MILU_BRAND.pageBg};
  --milu-icon-bg-start: ${MILU_BRAND.iconBgStart};
  --milu-icon-bg-end: ${MILU_BRAND.iconBgEnd};
}
html.dark-mode {
  --milu-primary: ${MILU_BRAND.primaryDark};
  --milu-primary-rgb: ${MILU_BRAND.primaryDarkRgb};
  --milu-page-bg: ${MILU_BRAND.pageBgDark};
}
* {
  margin: 0;
  box-sizing: border-box;
}
`;

function AuthGuard({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<"loading" | "auth-required" | "ok">(
    "loading",
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await authApi.getStatus();
        if (cancelled) return;
        if (!res.enabled) {
          setStatus("ok");
          return;
        }
        const token = getApiToken();
        if (!token) {
          setStatus("auth-required");
          return;
        }
        try {
          const r = await fetch(getApiUrl("/auth/verify"), {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (cancelled) return;
          if (r.ok) {
            setStatus("ok");
          } else {
            clearAuthToken();
            setStatus("auth-required");
          }
        } catch {
          if (!cancelled) {
            clearAuthToken();
            setStatus("auth-required");
          }
        }
      } catch {
        if (!cancelled) setStatus("ok");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === "loading") return null;
  if (status === "auth-required")
    return (
      <Navigate
        to={`/login?redirect=${encodeURIComponent(window.location.pathname)}`}
        replace
      />
    );
  return <>{children}</>;
}

function getRouterBasename(pathname: string): string | undefined {
  return /^\/console(?:\/|$)/.test(pathname) ? "/console" : undefined;
}

function AppInner() {
  const basename = getRouterBasename(window.location.pathname);
  const { i18n } = useTranslation();
  const { isDark } = useTheme();
  const lang = i18n.resolvedLanguage || i18n.language || "en";
  const [antdLocale, setAntdLocale] = useState<Locale>(
    antdLocaleMap[lang] ?? enUS,
  );

  useEffect(() => {
    if (!localStorage.getItem("language")) {
      languageApi
        .getLanguage()
        .then(({ language }) => {
          if (language && language !== i18n.language) {
            i18n.changeLanguage(language);
            localStorage.setItem("language", language);
          }
        })
        .catch((err) =>
          console.error("Failed to fetch language preference:", err),
        );
    }
  }, []);

  useEffect(() => {
    const handleLanguageChanged = (lng: string) => {
      const shortLng = lng.split("-")[0];
      setAntdLocale(antdLocaleMap[shortLng] ?? enUS);
      dayjs.locale(dayjsLocaleMap[shortLng] ?? "en");
    };

    // Set initial dayjs locale
    dayjs.locale(dayjsLocaleMap[lang.split("-")[0]] ?? "en");

    i18n.on("languageChanged", handleLanguageChanged);
    return () => {
      i18n.off("languageChanged", handleLanguageChanged);
    };
  }, [i18n]);

  const bailianThemeConfig = (bailianTheme as { theme?: object }).theme ?? {};
  const menuTokensLight = {
    itemBg: MILU_BRAND.pageBg,
    subMenuItemBg: MILU_BRAND.pageBg,
    popupBg: MILU_BRAND.pageBg,
    itemHoverBg: "rgba(85, 100, 168, 0.09)",
    itemActiveBg: "rgba(85, 100, 168, 0.06)",
    itemSelectedBg: "rgba(26, 43, 88, 0.09)",
    itemSelectedColor: MILU_BRAND.primary,
    itemHoverColor: MILU_BRAND.primary,
    groupTitleColor: "rgba(26, 43, 88, 0.42)",
  };
  const menuTokensDark = {
    itemBg: "transparent",
    subMenuItemBg: "transparent",
    popupBg: MILU_BRAND.pageBgDark,
    itemHoverBg: "rgba(255, 255, 255, 0.08)",
    itemActiveBg: "rgba(255, 255, 255, 0.06)",
    itemSelectedBg: "rgba(155, 139, 212, 0.24)",
    itemSelectedColor: MILU_BRAND.primaryDark,
    itemHoverColor: "#d6cef0",
    groupTitleColor: "rgba(255, 255, 255, 0.45)",
  };

  return (
    <BrowserRouter basename={basename}>
      <GlobalStyle />
      <ConfigProvider
        {...bailianTheme}
        prefix="milu"
        prefixCls="milu"
        locale={antdLocale}
        theme={{
          ...bailianThemeConfig,
          algorithm: isDark
            ? antdTheme.darkAlgorithm
            : antdTheme.defaultAlgorithm,
          token: {
            ...(bailianThemeConfig as { token?: object }).token,
            colorPrimary: isDark
              ? MILU_BRAND.primaryDark
              : MILU_BRAND.primary,
            colorLink: isDark
              ? MILU_BRAND.primaryDark
              : MILU_BRAND.primary,
            colorInfo: isDark
              ? MILU_BRAND.primaryDark
              : MILU_BRAND.primary,
          },
          components: {
            ...(bailianThemeConfig as { components?: object }).components,
            Menu: isDark ? menuTokensDark : menuTokensLight,
          },
        }}
      >
        <AntdApp>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/*"
              element={
                <AuthGuard>
                  <MainLayout />
                </AuthGuard>
              }
            />
          </Routes>
        </AntdApp>
      </ConfigProvider>
    </BrowserRouter>
  );
}

function App() {
  return (
    <ThemeProvider>
      <AppInner />
    </ThemeProvider>
  );
}

export default App;
