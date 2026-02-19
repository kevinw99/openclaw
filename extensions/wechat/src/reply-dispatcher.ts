import {
  createReplyPrefixContext,
  type ClawdbotConfig,
  type RuntimeEnv,
  type ReplyPayload,
} from "openclaw/plugin-sdk";
import { getWeChatRuntime } from "./runtime.js";
import { sendWeChatMessage } from "./send.js";
import { getBot } from "./client.js";

export type CreateWeChatReplyDispatcherParams = {
  cfg: ClawdbotConfig;
  agentId: string;
  runtime: RuntimeEnv;
  chatId: string;
  accountId?: string;
};

export function createWeChatReplyDispatcher(params: CreateWeChatReplyDispatcherParams) {
  const core = getWeChatRuntime();
  const { cfg, agentId, chatId, accountId } = params;

  const prefixContext = createReplyPrefixContext({
    cfg,
    agentId,
  });

  const textChunkLimit = core.channel.text.resolveTextChunkLimit(cfg, "wechat", accountId, {
    fallbackLimit: 2000,
  });
  const chunkMode = core.channel.text.resolveChunkMode(cfg, "wechat");
  const tableMode = core.channel.text.resolveMarkdownTableMode({ cfg, channel: "wechat" });

  const { dispatcher, replyOptions, markDispatchIdle } =
    core.channel.reply.createReplyDispatcherWithTyping({
      responsePrefix: prefixContext.responsePrefix,
      responsePrefixContextProvider: prefixContext.responsePrefixContextProvider,
      humanDelay: core.channel.reply.resolveHumanDelayConfig(cfg, agentId),
      deliver: async (payload: ReplyPayload) => {
        params.runtime.log?.(
          `wechat[${accountId ?? "default"}] deliver: text=${payload.text?.slice(0, 100)}`,
        );
        const text = payload.text ?? "";
        if (!text.trim()) {
          return;
        }

        const bot = getBot(accountId ?? "default");

        // Send media if present
        const mediaList = payload.mediaUrls?.length
          ? payload.mediaUrls
          : payload.mediaUrl
            ? [payload.mediaUrl]
            : [];
        for (const mediaUrl of mediaList) {
          await sendWeChatMessage({
            to: chatId,
            text: "",
            accountId,
            mediaPath: mediaUrl,
            bot: bot ?? undefined,
          });
        }

        // Send text chunks
        const converted = core.channel.text.convertMarkdownTables(text, tableMode);
        const chunks = core.channel.text.chunkTextWithMode(converted, textChunkLimit, chunkMode);
        params.runtime.log?.(
          `wechat[${accountId ?? "default"}] deliver: sending ${chunks.length} text chunks to ${chatId}`,
        );
        for (const chunk of chunks) {
          await sendWeChatMessage({
            to: chatId,
            text: chunk,
            accountId,
            bot: bot ?? undefined,
          });
        }
      },
      onError: (err, info) => {
        params.runtime.error?.(
          `wechat[${accountId ?? "default"}] ${info.kind} reply failed: ${String(err)}`,
        );
      },
    });

  return {
    dispatcher,
    replyOptions: {
      ...replyOptions,
      onModelSelected: prefixContext.onModelSelected,
    },
    markDispatchIdle,
  };
}
