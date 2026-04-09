import dayjs from "dayjs";

export { TIMEZONE_OPTIONS } from "../../../../constants/timezone";

export const DEFAULT_REQUEST_INPUT = `[
  {
    "role": "user",
    "content": [
      {
        "type": "text",
        "text": "请告诉我上海今天天气情况，包括温度和是否下雨"
      }
    ]
  }
]`;

export const DEFAULT_FORM_VALUES = {
  enabled: false,
  schedule: {
    type: "cron" as const,
    cron: "0 9 * * *",
    timezone: "UTC",
  },
  cronType: "daily",
  cronTime: dayjs().hour(9).minute(0),
  task_type: "agent" as const,
  request: {
    input: DEFAULT_REQUEST_INPUT,
  },
  dispatch: {
    type: "channel" as const,
    channel: "console",
    target: {
      user_id: "admin",
      session_id: "",
    },
    mode: "stream" as const,
  },
  runtime: {
    max_concurrency: 1,
    timeout_seconds: 300,
    misfire_grace_seconds: 60,
  },
};
