import { useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { consoleApi } from "../../api/modules/console";

const POLL_INTERVAL_MS = 2500;
const MAX_SEEN_IDS = 500;

/**
 * Invisible component: polls push-messages and auto-navigates to
 * the chat page when a cron job starts (type=cron_started).
 * No bubble/popup UI — all cron output goes to the chat window.
 */
export default function ConsoleCronBubble() {
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const seenIdsRef = useRef<Set<string>>(new Set());
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const tick = () => {
      consoleApi
        .getPushMessages()
        .then((res) => {
          if (!res?.messages?.length) return;
          const seen = seenIdsRef.current;
          if (seen.size > MAX_SEEN_IDS) seen.clear();
          for (const m of res.messages) {
            if (seen.has(m.id)) continue;
            seen.add(m.id);

            if (m.type === "cron_started" && m.session_id) {
              const chatPath = `/chat/${encodeURIComponent(m.session_id)}`;
              if (!location.pathname.startsWith(chatPath)) {
                navigate(chatPath);
              }
            }
          }
        })
        .catch(() => {});
    };

    tick();
    pollRef.current = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [navigate, location.pathname]);

  return null;
}
