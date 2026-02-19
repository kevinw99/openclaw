import type { ChannelOutboundAdapter } from "openclaw/plugin-sdk";
import { getWeChatRuntime } from "./runtime.js";
import { sendWeChatMessage } from "./send.js";

export const wechatOutbound: ChannelOutboundAdapter = {
  deliveryMode: "direct",
  chunker: (text, limit) => getWeChatRuntime().channel.text.chunkMarkdownText(text, limit),
  chunkerMode: "text",
  textChunkLimit: 2000,
  sendText: async ({ to, text, accountId }) => {
    const result = await sendWeChatMessage({
      to,
      text,
      accountId: accountId ?? undefined,
    });
    return {
      channel: "wechat",
      ok: result.ok,
      messageId: "",
      error: result.error ? new Error(result.error) : undefined,
    };
  },
  sendMedia: async ({ to, text, mediaUrl, accountId }) => {
    const result = await sendWeChatMessage({
      to,
      text: text ?? "",
      accountId: accountId ?? undefined,
      mediaPath: mediaUrl,
    });
    return {
      channel: "wechat",
      ok: result.ok,
      messageId: "",
      error: result.error ? new Error(result.error) : undefined,
    };
  },
};
