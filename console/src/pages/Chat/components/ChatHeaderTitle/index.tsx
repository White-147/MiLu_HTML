import React from "react";
import { useChatAnywhereSessionsState } from "@agentscope-ai/chat/lib/AgentScopeRuntimeWebUI";
import styles from "./index.module.less";

const ChatHeaderTitle: React.FC = () => {
  const { sessions, currentSessionId } = useChatAnywhereSessionsState();
  const currentSession = sessions.find((s) => s.id === currentSessionId);
  const chatName = currentSession?.name || "New Chat";

  return <span className={styles.chatName}>{chatName}</span>;
};

export default ChatHeaderTitle;
