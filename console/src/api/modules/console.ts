import { request } from "../request";

export interface PushMessage {
  id: string;
  text: string;
  type?: string;
  session_id?: string;
}

export const consoleApi = {
  getPushMessages: () =>
    request<{ messages: PushMessage[] }>("/console/push-messages"),
};
