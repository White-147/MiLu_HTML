import type { TFunction } from "i18next";

import { MILU_BRAND } from "@/constants/brandColors";

const defaultConfig = {
  theme: {
    colorPrimary: MILU_BRAND.primary,
    darkMode: false,
    prefix: "milu",
    leftHeader: {
      logo: "",
      title: "Work with MiLu",
    },
  },
  sender: {
    attachments: true,
    maxLength: 10000,
    disclaimer: "Works for you, grows with you",
  },
  welcome: {
    greeting: "Hello, how can I help you today?",
    description:
      "I am a helpful assistant that can help you with your questions.",
    avatar: `${import.meta.env.BASE_URL}milu-logo.png?v=${__MILU_STATIC_ASSET_STAMP__}`,
    prompts: [
      {
        value: "Let's start a new journey!",
      },
      {
        value: "Can you tell me what skills you have?",
      },
    ],
  },
  api: {
    baseURL: "",
    token: "",
  },
} as const;

export function getDefaultConfig(t: TFunction) {
  return {
    ...defaultConfig,
    sender: {
      ...defaultConfig.sender,
      disclaimer: t("chat.disclaimer"),
    },
    welcome: {
      ...defaultConfig.welcome,
      greeting: t("chat.greeting"),
      description: t("chat.description"),
      prompts: [{ value: t("chat.prompt1") }, { value: t("chat.prompt2") }],
    },
  };
}

export default defaultConfig;

export type DefaultConfig = typeof defaultConfig;
