import { useEffect, useMemo, useState } from "react";
import {
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
  Button,
  Checkbox,
} from "@agentscope-ai/design";
import { Modal, TimePicker, Tabs, Typography } from "antd";
import {
  QuestionCircleOutlined,
  ScanOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import type { FormInstance } from "antd";
import type { CronJobSpecOutput, ChatSpec } from "../../../../api/types";
import api from "../../../../api";
import { TIMEZONE_OPTIONS, DEFAULT_FORM_VALUES } from "./constants";
import styles from "../index.module.less";

type CronJob = CronJobSpecOutput;

const CONTENT_TYPE_EXAMPLES = {
  text: {
    label: "text",
    desc: "普通对话 / 指令 / 提问 / 总结 / 写作",
    json: JSON.stringify(
      [
        {
          role: "user",
          content: [{ type: "text", text: "请告诉我上海今天天气情况" }],
        },
      ],
      null,
      2,
    ),
  },
  image_url: {
    label: "image_url",
    desc: "让 AI 看图 / OCR / 分析截图 / 识别物体",
    json: JSON.stringify(
      [
        {
          role: "user",
          content: [
            { type: "text", text: "这张图里有什么？" },
            {
              type: "image_url",
              image_url: { url: "https://example.com/image.png" },
            },
          ],
        },
      ],
      null,
      2,
    ),
  },
  input_audio: {
    label: "input_audio",
    desc: "语音转文字 / 语音内容理解 / 会议记录",
    json: JSON.stringify(
      [
        {
          role: "user",
          content: [
            {
              type: "input_audio",
              input_audio: { data: "<base64编码>", format: "wav" },
            },
          ],
        },
      ],
      null,
      2,
    ),
  },
  file: {
    label: "file",
    desc: "PDF 分析 / Excel 处理 / 文档总结",
    json: JSON.stringify(
      [
        {
          role: "user",
          content: [
            { type: "text", text: "请总结这份文档的主要内容" },
            { type: "file", file: { file_id: "file-xxx" } },
          ],
        },
      ],
      null,
      2,
    ),
  },
  combined: {
    label: "组合使用",
    desc: "content 是数组，可以混合多种类型",
    json: JSON.stringify(
      [
        {
          role: "user",
          content: [
            { type: "text", text: "这张图里的天气怎么样？" },
            {
              type: "image_url",
              image_url: { url: "https://example.com/weather.png" },
            },
          ],
        },
      ],
      null,
      2,
    ),
  },
};

function ContentTypeModal({
  open,
  onClose,
  onInsert,
}: {
  open: boolean;
  onClose: () => void;
  onInsert: (json: string) => void;
}) {
  const { t } = useTranslation();
  const tabs = Object.entries(CONTENT_TYPE_EXAMPLES).map(([key, val]) => ({
    key,
    label: val.label,
    children: (
      <div>
        <Typography.Text
          type="secondary"
          style={{ display: "block", marginBottom: 8 }}
        >
          {t("cronJobs.typeDesc")}: {val.desc}
        </Typography.Text>
        <pre className={styles.codePreBlock}>
          {val.json}
        </pre>
        <Button
          type="primary"
          size="small"
          style={{ marginTop: 8 }}
          onClick={() => {
            onInsert(val.json);
            onClose();
          }}
        >
          {t("cronJobs.useThisTemplate")}
        </Button>
      </div>
    ),
  }));

  return (
    <Modal
      title={t("cronJobs.contentTypeReference")}
      open={open}
      onCancel={onClose}
      footer={null}
      width={620}
    >
      <Tabs items={tabs} />
    </Modal>
  );
}

/** Extract text content from request JSON. */
function extractTextFromRequestJson(jsonStr: string): string {
  try {
    const parsed = JSON.parse(jsonStr);
    const parts: string[] = [];
    const arr = Array.isArray(parsed) ? parsed : [parsed];
    for (const msg of arr) {
      const content = msg?.content;
      if (typeof content === "string") {
        parts.push(content);
        continue;
      }
      if (!Array.isArray(content)) continue;
      for (const c of content) {
        if (c.type === "text" && c.text) {
          parts.push(c.text);
        } else if (c.type === "image_url") {
          parts.push(`[图片: ${c.image_url?.url || "..."}]`);
        } else if (c.type === "input_audio") {
          parts.push(`[音频: ${c.input_audio?.format || "audio"}]`);
        } else if (c.type === "file") {
          parts.push(`[文件: ${c.file?.file_id || "..."}]`);
        }
      }
    }
    return parts.join("\n");
  } catch {
    return "";
  }
}

interface JobDrawerProps {
  open: boolean;
  editingJob: CronJob | null;
  form: FormInstance<CronJob>;
  saving: boolean;
  onClose: () => void;
  onSubmit: (values: CronJob) => void;
}

const DEFAULT_REQUEST_INPUT = `[
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

const NEW_SESSION_VALUE = "__new_session__";

export function JobDrawer({
  open,
  editingJob,
  form,
  saving,
  onClose,
  onSubmit,
}: JobDrawerProps) {
  const { t } = useTranslation();
  const [sessions, setSessions] = useState<ChatSpec[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [typeModalOpen, setTypeModalOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoadingSessions(true);
    api
      .listSessions()
      .then((list) => setSessions(list ?? []))
      .catch(() => setSessions([]))
      .finally(() => setLoadingSessions(false));
  }, [open]);

  const userIdOptions = useMemo(() => {
    const ids = new Set<string>();
    sessions.forEach((s) => {
      if (s.user_id) ids.add(s.user_id);
    });
    if (ids.size === 0) ids.add("admin");
    return Array.from(ids).map((id) => ({ label: id, value: id }));
  }, [sessions]);

  const sessionIdOptions = useMemo(() => {
    const opts = sessions.map((s) => ({
      label: s.name
        ? `${s.name} (${s.id})`
        : `${s.channel}:${s.user_id} (${s.id})`,
      value: s.id,
    }));
    opts.unshift({
      label: `✨ ${t("cronJobs.newSession")}`,
      value: NEW_SESSION_VALUE,
    });
    return opts;
  }, [sessions, t]);

  const handleAutoFillText = () => {
    const val = form.getFieldValue(["request", "input"]);
    if (!val) return;
    const text = extractTextFromRequestJson(val);
    if (text) {
      form.setFieldValue("text", text);
    }
  };

  return (
    <Drawer
      width={600}
      placement="right"
      title={editingJob ? t("cronJobs.editJob") : t("cronJobs.createJob")}
      open={open}
      onClose={onClose}
      destroyOnClose
      footer={
        <div className={styles.formActions}>
          <Button onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="primary" loading={saving} onClick={() => form.submit()}>
            {t("common.save")}
          </Button>
        </div>
      }
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={onSubmit}
        initialValues={DEFAULT_FORM_VALUES}
      >
        <Form.Item
          name="name"
          label={t("cronJobs.name")}
          rules={[{ required: true, message: t("cronJobs.pleaseInputName") }]}
          tooltip={t("cronJobs.nameTooltip")}
        >
          <Input placeholder={t("cronJobs.jobNamePlaceholder")} />
        </Form.Item>

        <Form.Item
          name="enabled"
          label={t("cronJobs.enabled")}
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>

        <Form.Item name={["schedule", "type"]} label="ScheduleType" hidden>
          <Input disabled value="cron" />
        </Form.Item>

        <Form.Item
          label={t("cronJobs.scheduleCronLabel")}
          required
          tooltip={t("cronJobs.cronTooltip")}
        >
          <Form.Item name="cronType" noStyle>
            <Select>
              <Select.Option value="hourly">
                {t("cronJobs.cronTypeHourly")}
              </Select.Option>
              <Select.Option value="daily">
                {t("cronJobs.cronTypeDaily")}
              </Select.Option>
              <Select.Option value="weekly">
                {t("cronJobs.cronTypeWeekly")}
              </Select.Option>
              <Select.Option value="custom">
                {t("cronJobs.cronTypeCustom")}
              </Select.Option>
            </Select>
          </Form.Item>
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prev, cur) => prev.cronType !== cur.cronType}
        >
          {({ getFieldValue }) => {
            const cronType = getFieldValue("cronType");

            if (cronType === "daily" || cronType === "weekly") {
              return (
                <Form.Item
                  name="cronTime"
                  label={t("cronJobs.cronTime")}
                  rules={[{ required: true }]}
                >
                  <TimePicker
                    format="HH:mm"
                    minuteStep={15}
                    needConfirm={false}
                    style={{ width: "100%" }}
                  />
                </Form.Item>
              );
            }
            return null;
          }}
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prev, cur) => prev.cronType !== cur.cronType}
        >
          {({ getFieldValue }) => {
            const cronType = getFieldValue("cronType");

            if (cronType === "weekly") {
              return (
                <Form.Item
                  name="cronDaysOfWeek"
                  label={t("cronJobs.cronDaysOfWeek")}
                  rules={[{ required: true, message: t("cronJobs.pleaseSelectDays") }]}
                >
                  <Checkbox.Group
                    options={[
                      { label: t("cronJobs.cronDayMon"), value: "mon" },
                      { label: t("cronJobs.cronDayTue"), value: "tue" },
                      { label: t("cronJobs.cronDayWed"), value: "wed" },
                      { label: t("cronJobs.cronDayThu"), value: "thu" },
                      { label: t("cronJobs.cronDayFri"), value: "fri" },
                      { label: t("cronJobs.cronDaySat"), value: "sat" },
                      { label: t("cronJobs.cronDaySun"), value: "sun" },
                    ]}
                  />
                </Form.Item>
              );
            }
            return null;
          }}
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prev, cur) => prev.cronType !== cur.cronType}
        >
          {({ getFieldValue }) => {
            const cronType = getFieldValue("cronType");

            if (cronType === "custom") {
              return (
                <Form.Item
                  name="cronCustom"
                  label={t("cronJobs.cronCustomExpression")}
                  rules={[
                    { required: true, message: t("cronJobs.pleaseInputCron") },
                  ]}
                  extra={
                    <div className={styles.formExtraText}>
                      <div style={{ marginBottom: 4 }}>
                        {t("cronJobs.cronExample")}
                      </div>
                      <div>
                        {t("cronJobs.cronHelper")}{" "}
                        <a
                          href="https://crontab.guru/"
                          target="_blank"
                          rel="noopener noreferrer"
                          className={styles.formHelperLink}
                        >
                          {t("cronJobs.cronHelperLink")} →
                        </a>
                      </div>
                    </div>
                  }
                >
                  <Input placeholder="0 9 * * *" />
                </Form.Item>
              );
            }
            return null;
          }}
        </Form.Item>

        <Form.Item name={["schedule", "cron"]} hidden>
          <Input />
        </Form.Item>

        <Form.Item
          name={["schedule", "timezone"]}
          label={t("cronJobs.scheduleTimezone")}
          tooltip={t("cronJobs.timezoneTooltip")}
        >
          <Select
            showSearch
            placeholder={t("cronJobs.selectTimezone")}
            filterOption={(input, option) =>
              (option?.label?.toString() || "")
                .toLowerCase()
                .includes(input.toLowerCase())
            }
            options={TIMEZONE_OPTIONS}
          />
        </Form.Item>

        <Form.Item
          name="task_type"
          label={t("cronJobs.taskType")}
          rules={[
            { required: true, message: t("cronJobs.pleaseSelectTaskType") },
          ]}
          tooltip={t("cronJobs.taskTypeTooltip")}
        >
          <Select>
            <Select.Option value="text">
              text - {t("cronJobs.taskTypeTextDesc")}
            </Select.Option>
            <Select.Option value="agent">
              agent - {t("cronJobs.taskTypeAgentDesc")}
            </Select.Option>
          </Select>
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prev, cur) => prev.task_type !== cur.task_type}
        >
          {({ getFieldValue }) => {
            const taskType = getFieldValue("task_type");
            const textRequired = taskType === "text";
            const agentRequired = taskType === "agent";

            return (
              <>
                <Form.Item
                  name="text"
                  label={
                    <span>
                      {t("cronJobs.text")}
                      <Button
                        type="link"
                        size="small"
                        icon={<ScanOutlined />}
                        style={{ marginLeft: 4, padding: 0 }}
                        onClick={handleAutoFillText}
                      >
                        {t("cronJobs.autoDetectContent")}
                      </Button>
                    </span>
                  }
                  required={textRequired}
                  rules={
                    textRequired
                      ? [
                          {
                            required: true,
                            message: t("cronJobs.pleaseInputMessageContent"),
                          },
                        ]
                      : []
                  }
                  tooltip={t("cronJobs.textTooltip")}
                >
                  <Input.TextArea
                    rows={3}
                    placeholder={t("cronJobs.taskDescriptionPlaceholder")}
                  />
                </Form.Item>

                <Form.Item
                  name={["request", "input"]}
                  label={
                    <span>
                      {t("cronJobs.requestInput")}
                      <Button
                        type="link"
                        size="small"
                        icon={<QuestionCircleOutlined />}
                        style={{ marginLeft: 4, padding: 0 }}
                        onClick={() => setTypeModalOpen(true)}
                      >
                        {t("cronJobs.viewTypeReference")}
                      </Button>
                    </span>
                  }
                  required={agentRequired}
                  rules={[
                    ...(agentRequired
                      ? [
                          {
                            required: true,
                            message: t("cronJobs.pleaseInputRequest"),
                          },
                        ]
                      : []),
                    {
                      validator: (_: unknown, value: string) => {
                        if (!value) return Promise.resolve();
                        try {
                          JSON.parse(value);
                          return Promise.resolve();
                        } catch {
                          return Promise.reject(
                            new Error(t("cronJobs.invalidJsonFormat")),
                          );
                        }
                      },
                    },
                  ]}
                  tooltip={t("cronJobs.requestInputTooltip")}
                  extra={
                    <div className={styles.formExtraText}>
                      <div>{t("cronJobs.requestInputHint")}</div>
                    </div>
                  }
                >
                  <Input.TextArea
                    rows={8}
                    placeholder={DEFAULT_REQUEST_INPUT}
                    style={{ fontFamily: "monospace", fontSize: 12 }}
                  />
                </Form.Item>

                <ContentTypeModal
                  open={typeModalOpen}
                  onClose={() => setTypeModalOpen(false)}
                  onInsert={(json) => {
                    form.setFieldValue(["request", "input"], json);
                  }}
                />
              </>
            );
          }}
        </Form.Item>

        <Form.Item name={["dispatch", "type"]} label="DispatchType" hidden>
          <Input disabled value="channel" />
        </Form.Item>

        <Form.Item
          name={["dispatch", "channel"]}
          label={t("cronJobs.dispatchChannel")}
          rules={[
            { required: true, message: t("cronJobs.pleaseInputChannel") },
          ]}
          tooltip={t("cronJobs.dispatchChannelTooltip")}
        >
          <Input placeholder="console" />
        </Form.Item>

        <Form.Item
          name={["dispatch", "target", "user_id"]}
          label={t("cronJobs.dispatchTargetUserId")}
          rules={[{ required: true, message: t("cronJobs.pleaseInputUserId") }]}
          tooltip={t("cronJobs.dispatchTargetUserIdTooltip")}
        >
          <Select
            showSearch
            allowClear
            loading={loadingSessions}
            placeholder={t("cronJobs.selectUserId")}
            options={userIdOptions}
            filterOption={(input, option) =>
              (option?.label?.toString() || "")
                .toLowerCase()
                .includes(input.toLowerCase())
            }
          />
        </Form.Item>

        <Form.Item
          name={["dispatch", "target", "session_id"]}
          label={t("cronJobs.dispatchTargetSessionId")}
          rules={[
            { required: true, message: t("cronJobs.pleaseInputSessionId") },
          ]}
          tooltip={t("cronJobs.dispatchTargetSessionIdTooltip")}
        >
          <Select
            showSearch
            loading={loadingSessions}
            placeholder={t("cronJobs.selectSessionId")}
            options={sessionIdOptions}
            filterOption={(input, option) =>
              (option?.label?.toString() || "")
                .toLowerCase()
                .includes(input.toLowerCase())
            }
          />
        </Form.Item>

        <Form.Item
          name={["dispatch", "mode"]}
          label={t("cronJobs.dispatchMode")}
          tooltip={t("cronJobs.dispatchModeTooltip")}
        >
          <Select>
            <Select.Option value="stream">stream</Select.Option>
            <Select.Option value="final">final</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item
          name={["runtime", "max_concurrency"]}
          label={t("cronJobs.runtimeMaxConcurrency")}
          tooltip={t("cronJobs.maxConcurrencyTooltip")}
        >
          <InputNumber min={1} style={{ width: "100%" }} placeholder="1" />
        </Form.Item>

        <Form.Item
          name={["runtime", "timeout_seconds"]}
          label={t("cronJobs.runtimeTimeoutSeconds")}
          tooltip={t("cronJobs.timeoutSecondsTooltip")}
        >
          <InputNumber min={1} style={{ width: "100%" }} placeholder="300" />
        </Form.Item>

        <Form.Item
          name={["runtime", "misfire_grace_seconds"]}
          label={t("cronJobs.runtimeMisfireGraceSeconds")}
          tooltip={t("cronJobs.misfireGraceSecondsTooltip")}
        >
          <InputNumber min={0} style={{ width: "100%" }} placeholder="60" />
        </Form.Item>
      </Form>
    </Drawer>
  );
}
