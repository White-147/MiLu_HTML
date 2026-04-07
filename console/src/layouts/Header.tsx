import { Layout, Space, Tooltip } from "antd";
import LanguageSwitcher from "../components/LanguageSwitcher/index";
import ThemeToggleButton from "../components/ThemeToggleButton";
import { useTranslation } from "react-i18next";
import { Button } from "@agentscope-ai/design";
import styles from "./index.module.less";
import { getDocsUrl } from "./constants";
import { useTheme } from "../contexts/ThemeContext";

const { Header: AntHeader } = Layout;

export default function Header() {
  const { t } = useTranslation();
  const { isDark } = useTheme();

  const logoSrc = `${import.meta.env.BASE_URL}${
    isDark ? "dark-logo.png" : "logo.png"
  }?v=${__MILU_STATIC_ASSET_STAMP__}`;

  const handleNavClick = (url: string) => {
    if (!url) return;
    const target =
      /^https?:\/\//i.test(url)
        ? url
        : new URL(url, window.location.origin).href;
    const pywebview = (window as any).pywebview;
    if (pywebview?.api) {
      pywebview.api.open_external_link(target);
    } else {
      window.open(target, "_blank");
    }
  };

  return (
    <AntHeader className={styles.header}>
      <div className={styles.logoWrapper}>
        <img
          key={logoSrc}
          src={logoSrc}
          alt="MiLu"
          className={styles.logoImg}
        />
      </div>
      <Space size="middle">
        <Tooltip title={t("header.docs")}>
          <Button
            type="text"
            onClick={() => handleNavClick(getDocsUrl())}
          >
            {t("header.docs")}
          </Button>
        </Tooltip>
        <div className={styles.headerDivider} />
        <LanguageSwitcher />
        <ThemeToggleButton />
      </Space>
    </AntHeader>
  );
}
