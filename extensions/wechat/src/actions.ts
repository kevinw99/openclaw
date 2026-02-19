import type {
  ChannelMessageActionAdapter,
  ChannelMessageActionName,
  OpenClawConfig,
} from "openclaw/plugin-sdk";
import { jsonResult, readStringParam } from "openclaw/plugin-sdk";
import { listEnabledWeChatAccounts } from "./accounts.js";
import { sendWeChatMessage } from "./send.js";

const providerId = "wechat";

function listEnabledAccounts(cfg: OpenClawConfig) {
  return listEnabledWeChatAccounts(cfg).filter(
    (account) => account.enabled && account.tokenSource !== "none",
  );
}

export const wechatMessageActions: ChannelMessageActionAdapter = {
  listActions: ({ cfg }) => {
    const accounts = listEnabledAccounts(cfg);
    if (accounts.length === 0) {
      return [];
    }
    const actions = new Set<ChannelMessageActionName>(["send"]);
    return Array.from(actions);
  },
  supportsButtons: () => false,
  extractToolSend: ({ args }) => {
    const action = typeof args.action === "string" ? args.action.trim() : "";
    if (action !== "sendMessage") {
      return null;
    }
    const to = typeof args.to === "string" ? args.to : undefined;
    if (!to) {
      return null;
    }
    const accountId = typeof args.accountId === "string" ? args.accountId.trim() : undefined;
    return { to, accountId };
  },
  handleAction: async ({ action, params, accountId }) => {
    if (action === "send") {
      const to = readStringParam(params, "to", { required: true });
      const content = readStringParam(params, "message", {
        required: true,
        allowEmpty: true,
      });
      const mediaPath = readStringParam(params, "media", { trim: false });

      const result = await sendWeChatMessage({
        to: to ?? "",
        text: content ?? "",
        accountId: accountId ?? undefined,
        mediaPath: mediaPath ?? undefined,
      });

      if (!result.ok) {
        return jsonResult({
          ok: false,
          error: result.error ?? "Failed to send WeChat message",
        });
      }

      return jsonResult({ ok: true, to });
    }

    throw new Error(`Action ${action} is not supported for provider ${providerId}.`);
  },
};
