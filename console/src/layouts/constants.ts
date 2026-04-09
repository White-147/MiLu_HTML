// ── Docs (header) ─────────────────────────────────────────────────────────
// Repo file (relative to project root):
// website/exported-docs/milu-docs-zh/milu-docs-zh-all.docx
// Served by the MiLu app at the path below (same-origin).

export const MILU_DOCS_ZH_URL_PATH = "milu-docs-zh";

export const getDocsUrl = (): string =>
  `${import.meta.env.BASE_URL}${MILU_DOCS_ZH_URL_PATH}`;

// ── Navigation ────────────────────────────────────────────────────────────

export const DEFAULT_OPEN_KEYS = [
  "chat-group",
  "control-group",
  "agent-group",
  "settings-group",
];

export const KEY_TO_PATH: Record<string, string> = {
  chat: "/chat",
  channels: "/channels",
  sessions: "/sessions",
  "cron-jobs": "/cron-jobs",
  heartbeat: "/heartbeat",
  skills: "/skills",
  tools: "/tools",
  mcp: "/mcp",
  workspace: "/workspace",
  agents: "/agents",
  models: "/models",
  environments: "/environments",
  "agent-config": "/agent-config",
  security: "/security",
  "token-usage": "/token-usage",
  "voice-transcription": "/voice-transcription",
};

export const KEY_TO_LABEL: Record<string, string> = {
  chat: "nav.chat",
  channels: "nav.channels",
  sessions: "nav.sessions",
  "cron-jobs": "nav.cronJobs",
  heartbeat: "nav.heartbeat",
  skills: "nav.skills",
  tools: "nav.tools",
  mcp: "nav.mcp",
  "agent-config": "nav.agentConfig",
  workspace: "nav.workspace",
  models: "nav.models",
  environments: "nav.environments",
  security: "nav.security",
  "token-usage": "nav.tokenUsage",
  agents: "nav.agents",
};
