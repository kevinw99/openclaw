import type { Message, Wechaty } from "wechaty";
import { types as WechatyTypes } from "wechaty";
import type { OpenClawConfig, MarkdownTableMode } from "openclaw/plugin-sdk";
import { createReplyPrefixOptions } from "openclaw/plugin-sdk";
import type { ResolvedWeChatAccount } from "./accounts.js";
import { createWechatyBot, stopBot } from "./bot.js";
import { getWeChatRuntime } from "./runtime.js";
import { sendWeChatMessage } from "./send.js";
import { transcribeVoiceMessage } from "./voice.js";
import { startMomentsPoller } from "./moments.js";
import { buildContactIndex } from "./contact-graph.js";

export type WeChatRuntimeEnv = {
  log?: (message: string) => void;
  error?: (message: string) => void;
};

export type WeChatMonitorOptions = {
  account: ResolvedWeChatAccount;
  config: OpenClawConfig;
  runtime: WeChatRuntimeEnv;
  abortSignal: AbortSignal;
  statusSink?: (patch: {
    lastInboundAt?: number;
    lastOutboundAt?: number;
    loggedIn?: boolean;
    user?: { id: string; name: string };
  }) => void;
};

export type WeChatMonitorResult = {
  stop: () => void;
};

const WECHAT_TEXT_LIMIT = 2000;
const DEFAULT_MEDIA_MAX_MB = 50;
const MAX_MESSAGE_AGE_SECONDS = 60;

type WeChatCoreRuntime = ReturnType<typeof getWeChatRuntime>;

function logVerbose(
  core: WeChatCoreRuntime,
  runtime: WeChatRuntimeEnv,
  message: string,
): void {
  if (core.logging.shouldLogVerbose()) {
    runtime.log?.(`[wechat] ${message}`);
  }
}

function isSenderAllowed(senderId: string, allowFrom: string[]): boolean {
  if (allowFrom.includes("*")) {
    return true;
  }
  const normalizedSenderId = senderId.toLowerCase();
  return allowFrom.some((entry) => {
    const normalized = entry.toLowerCase().replace(/^(wechat|wx):/i, "");
    return normalized === normalizedSenderId;
  });
}

async function processMessage(
  msg: Message,
  bot: Wechaty,
  account: ResolvedWeChatAccount,
  config: OpenClawConfig,
  runtime: WeChatRuntimeEnv,
  core: WeChatCoreRuntime,
  mediaMaxMb: number,
  statusSink?: WeChatMonitorOptions["statusSink"],
): Promise<void> {
  // Skip own messages
  if (msg.self()) {
    return;
  }

  // Skip stale messages
  if (msg.age() > MAX_MESSAGE_AGE_SECONDS) {
    return;
  }

  const msgType = msg.type();

  let text: string | undefined;
  let mediaPath: string | undefined;
  let mediaType: string | undefined;

  switch (msgType) {
    case WechatyTypes.Message.Text: {
      text = msg.text()?.trim();
      if (!text) {
        return;
      }
      break;
    }

    case WechatyTypes.Message.Audio: {
      const voiceConfig = account.config.voice;
      if (voiceConfig?.transcribe === false) {
        text = "[Voice message]";
      } else {
        try {
          const transcript = await transcribeVoiceMessage(msg, voiceConfig ?? {});
          text = transcript ? `[Voice: ${transcript}]` : "[Voice message — transcription unavailable]";
        } catch {
          text = "[Voice message — transcription failed]";
        }
      }
      break;
    }

    case WechatyTypes.Message.Image:
    case WechatyTypes.Message.Video: {
      try {
        const fileBox = await msg.toFileBox();
        const buffer = await fileBox.toBuffer();
        const maxBytes = mediaMaxMb * 1024 * 1024;
        const contentType =
          msgType === WechatyTypes.Message.Image ? "image/jpeg" : "video/mp4";
        const saved = await core.channel.media.saveMediaBuffer(
          buffer,
          contentType,
          "inbound",
          maxBytes,
        );
        mediaPath = saved.path;
        mediaType = saved.contentType;
      } catch (err) {
        runtime.error?.(`[${account.accountId}] Failed to save WeChat media: ${String(err)}`);
      }
      text = msg.text()?.trim() || (mediaPath ? "<media>" : undefined);
      if (!text && !mediaPath) {
        return;
      }
      break;
    }

    case WechatyTypes.Message.Contact: {
      try {
        const sharedContact = await msg.toContact();
        const contactName = sharedContact?.name() ?? "unknown";
        const contactId = sharedContact?.id ?? "unknown";
        text = `<contact: ${contactName} (${contactId})>`;
      } catch {
        text = "<contact: unknown>";
      }
      break;
    }

    case WechatyTypes.Message.Url: {
      try {
        const urlLink = await msg.toUrlLink();
        const title = urlLink?.title() ?? "";
        const url = urlLink?.url() ?? "";
        text = `<link: ${title} — ${url}>`;
      } catch {
        text = "<link: unknown>";
      }
      break;
    }

    // Skip these message types
    case WechatyTypes.Message.Emoticon:
    case WechatyTypes.Message.Recalled:
    case WechatyTypes.Message.Unknown:
    default:
      return;
  }

  if (!text && !mediaPath) {
    return;
  }

  statusSink?.({ lastInboundAt: Date.now() });

  await processMessageWithPipeline({
    msg,
    bot,
    account,
    config,
    runtime,
    core,
    text: text ?? "",
    mediaPath,
    mediaType,
    statusSink,
  });
}

async function processMessageWithPipeline(params: {
  msg: Message;
  bot: Wechaty;
  account: ResolvedWeChatAccount;
  config: OpenClawConfig;
  runtime: WeChatRuntimeEnv;
  core: WeChatCoreRuntime;
  text: string;
  mediaPath?: string;
  mediaType?: string;
  statusSink?: WeChatMonitorOptions["statusSink"];
}): Promise<void> {
  const { msg, bot, account, config, runtime, core, text, mediaPath, mediaType, statusSink } =
    params;

  const room = msg.room();
  const from = msg.talker();
  const isGroup = room !== null;
  const senderId = from.id;
  const senderName = from.name();
  const chatId = isGroup ? room!.id : senderId;

  // Group @mention check
  if (isGroup) {
    const groupPolicy = account.config.groupPolicy ?? "allowlist";
    if (groupPolicy === "disabled") {
      return;
    }
    const requireMention = account.config.requireMention !== false;
    if (requireMention) {
      try {
        const mentionSelf = await msg.mentionSelf();
        if (!mentionSelf) {
          return;
        }
      } catch {
        // if mentionSelf fails, skip the message in groups
        return;
      }
    }
  }

  const dmPolicy = account.config.dmPolicy ?? "pairing";
  const configAllowFrom = account.config.allowFrom ?? [];
  const rawBody = text?.trim() || (mediaPath ? "<media:image>" : "");
  const shouldComputeAuth = core.channel.commands.shouldComputeCommandAuthorized(rawBody, config);
  const storeAllowFrom =
    !isGroup && (dmPolicy !== "open" || shouldComputeAuth)
      ? await core.channel.pairing.readAllowFromStore("wechat").catch(() => [])
      : [];
  const effectiveAllowFrom = [...configAllowFrom, ...storeAllowFrom];
  const useAccessGroups = config.commands?.useAccessGroups !== false;
  const senderAllowedForCommands = isSenderAllowed(senderId, effectiveAllowFrom);
  const commandAuthorized = shouldComputeAuth
    ? core.channel.commands.resolveCommandAuthorizedFromAuthorizers({
        useAccessGroups,
        authorizers: [
          { configured: effectiveAllowFrom.length > 0, allowed: senderAllowedForCommands },
        ],
      })
    : undefined;

  if (!isGroup) {
    if (dmPolicy === "disabled") {
      logVerbose(core, runtime, `Blocked wechat DM from ${senderId} (dmPolicy=disabled)`);
      return;
    }

    if (dmPolicy !== "open") {
      const allowed = senderAllowedForCommands;

      if (!allowed) {
        if (dmPolicy === "pairing") {
          const { code, created } = await core.channel.pairing.upsertPairingRequest({
            channel: "wechat",
            id: senderId,
            meta: { name: senderName ?? undefined },
          });

          if (created) {
            logVerbose(core, runtime, `wechat pairing request sender=${senderId}`);
            try {
              const contact = await bot.Contact.find({ id: senderId });
              if (contact) {
                await contact.say(
                  core.channel.pairing.buildPairingReply({
                    channel: "wechat",
                    idLine: `Your WeChat id: ${senderId}`,
                    code,
                  }),
                );
                statusSink?.({ lastOutboundAt: Date.now() });
              }
            } catch (err) {
              logVerbose(
                core,
                runtime,
                `wechat pairing reply failed for ${senderId}: ${String(err)}`,
              );
            }
          }
        } else {
          logVerbose(
            core,
            runtime,
            `Blocked unauthorized wechat sender ${senderId} (dmPolicy=${dmPolicy})`,
          );
        }
        return;
      }
    }
  }

  const route = core.channel.routing.resolveAgentRoute({
    cfg: config,
    channel: "wechat",
    accountId: account.accountId,
    peer: {
      kind: isGroup ? "group" : "direct",
      id: chatId,
    },
  });

  if (
    isGroup &&
    core.channel.commands.isControlCommandMessage(rawBody, config) &&
    commandAuthorized !== true
  ) {
    logVerbose(core, runtime, `wechat: drop control command from unauthorized sender ${senderId}`);
    return;
  }

  let fromLabel: string;
  if (isGroup) {
    let topic = "";
    try {
      topic = (await room!.topic()) || "";
    } catch {
      // ignore
    }
    fromLabel = topic ? `group:${topic}` : `group:${chatId}`;
  } else {
    fromLabel = senderName || `user:${senderId}`;
  }

  const storePath = core.channel.session.resolveStorePath(config.session?.store, {
    agentId: route.agentId,
  });
  const envelopeOptions = core.channel.reply.resolveEnvelopeFormatOptions(config);
  const previousTimestamp = core.channel.session.readSessionUpdatedAt({
    storePath,
    sessionKey: route.sessionKey,
  });
  const body = core.channel.reply.formatAgentEnvelope({
    channel: "WeChat",
    from: isGroup ? `${senderName} in ${fromLabel}` : fromLabel,
    timestamp: msg.date() ? msg.date().getTime() : undefined,
    previousTimestamp,
    envelope: envelopeOptions,
    body: rawBody,
  });

  const ctxPayload = core.channel.reply.finalizeInboundContext({
    Body: body,
    RawBody: rawBody,
    CommandBody: rawBody,
    From: isGroup ? `wechat:group:${chatId}` : `wechat:${senderId}`,
    To: `wechat:${chatId}`,
    SessionKey: route.sessionKey,
    AccountId: route.accountId,
    ChatType: isGroup ? "group" : "direct",
    ConversationLabel: fromLabel,
    SenderName: senderName || undefined,
    SenderId: senderId,
    CommandAuthorized: commandAuthorized,
    Provider: "wechat",
    Surface: "wechat",
    MessageSid: msg.id,
    MediaPath: mediaPath,
    MediaType: mediaType,
    MediaUrl: mediaPath,
    OriginatingChannel: "wechat",
    OriginatingTo: `wechat:${chatId}`,
  });

  await core.channel.session.recordInboundSession({
    storePath,
    sessionKey: ctxPayload.SessionKey ?? route.sessionKey,
    ctx: ctxPayload,
    onRecordError: (err) => {
      runtime.error?.(`wechat: failed updating session meta: ${String(err)}`);
    },
  });

  const tableMode = core.channel.text.resolveMarkdownTableMode({
    cfg: config,
    channel: "wechat",
    accountId: account.accountId,
  });
  const { onModelSelected, ...prefixOptions } = createReplyPrefixOptions({
    cfg: config,
    agentId: route.agentId,
    channel: "wechat",
    accountId: account.accountId,
  });

  await core.channel.reply.dispatchReplyWithBufferedBlockDispatcher({
    ctx: ctxPayload,
    cfg: config,
    dispatcherOptions: {
      ...prefixOptions,
      deliver: async (payload) => {
        await deliverWeChatReply({
          payload,
          bot,
          chatId,
          isGroup,
          runtime,
          core,
          config,
          accountId: account.accountId,
          statusSink,
          tableMode,
          minReplyDelayMs: account.config.minReplyDelayMs,
        });
      },
      onError: (err, info) => {
        runtime.error?.(
          `[${account.accountId}] WeChat ${info.kind} reply failed: ${String(err)}`,
        );
      },
    },
    replyOptions: {
      onModelSelected,
    },
  });
}

async function deliverWeChatReply(params: {
  payload: { text?: string; mediaUrls?: string[]; mediaUrl?: string };
  bot: Wechaty;
  chatId: string;
  isGroup: boolean;
  runtime: WeChatRuntimeEnv;
  core: WeChatCoreRuntime;
  config: OpenClawConfig;
  accountId?: string;
  statusSink?: WeChatMonitorOptions["statusSink"];
  tableMode?: MarkdownTableMode;
  minReplyDelayMs?: number;
}): Promise<void> {
  const { payload, bot, chatId, isGroup, runtime, core, config, accountId, statusSink } = params;
  const tableMode = params.tableMode ?? "code";
  const text = core.channel.text.convertMarkdownTables(payload.text ?? "", tableMode);
  const minDelay = params.minReplyDelayMs ?? 500;

  const mediaList = payload.mediaUrls?.length
    ? payload.mediaUrls
    : payload.mediaUrl
      ? [payload.mediaUrl]
      : [];

  if (minDelay > 0) {
    await new Promise((resolve) => setTimeout(resolve, minDelay));
  }

  if (mediaList.length > 0) {
    for (const mediaUrl of mediaList) {
      try {
        await sendWeChatMessage({
          to: chatId,
          text: "",
          accountId,
          mediaPath: mediaUrl,
          bot,
        });
        statusSink?.({ lastOutboundAt: Date.now() });
      } catch (err) {
        runtime.error?.(`WeChat media send failed: ${String(err)}`);
      }
    }
  }

  if (text) {
    const chunkMode = core.channel.text.resolveChunkMode(config, "wechat", accountId);
    const chunks = core.channel.text.chunkMarkdownTextWithMode(text, WECHAT_TEXT_LIMIT, chunkMode);
    for (const chunk of chunks) {
      try {
        await sendWeChatMessage({
          to: chatId,
          text: chunk,
          accountId,
          bot,
        });
        statusSink?.({ lastOutboundAt: Date.now() });
      } catch (err) {
        runtime.error?.(`WeChat message send failed: ${String(err)}`);
      }
    }
  }
}

export async function monitorWeChatProvider(
  options: WeChatMonitorOptions,
): Promise<WeChatMonitorResult> {
  const { account, config, runtime, abortSignal, statusSink } = options;

  const core = getWeChatRuntime();
  const effectiveMediaMaxMb = account.config.mediaMaxMb ?? DEFAULT_MEDIA_MAX_MB;

  let stopped = false;
  const stopHandlers: Array<() => void> = [];

  const stop = () => {
    stopped = true;
    for (const handler of stopHandlers) {
      handler();
    }
    void stopBot(account.accountId);
  };

  const bot = createWechatyBot(account);

  // QR code scan event
  bot.on("scan", (qrcode: string, status: number) => {
    if (stopped || abortSignal.aborted) {
      return;
    }
    runtime.log?.(`[${account.accountId}] WeChat QR scan needed (status=${status})`);
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const qrcodeTerminal = require("qrcode-terminal") as {
        generate: (text: string, opts: { small: boolean }) => void;
      };
      qrcodeTerminal.generate(qrcode, { small: true });
    } catch {
      runtime.log?.(`[${account.accountId}] QR code URL: https://wechaty.js.org/qrcode/${qrcode}`);
    }
  });

  // Login event
  bot.on("login", (user: { name: () => string; id: string }) => {
    const userName = user.name();
    runtime.log?.(`[${account.accountId}] WeChat logged in as ${userName} (${user.id})`);
    statusSink?.({ loggedIn: true, user: { id: user.id, name: userName } });

    // Start Moments poller if configured
    if (
      account.config.moments?.enabled &&
      account.puppet === "padlocal"
    ) {
      const momentsStop = startMomentsPoller(bot, account.config.moments, core);
      stopHandlers.push(momentsStop.stop);
    }

    // Build contact index if configured
    if (account.config.contacts?.indexEnabled !== false) {
      void buildContactIndex(bot, account.accountId).catch((err) => {
        runtime.error?.(`[${account.accountId}] Contact index build failed: ${String(err)}`);
      });
    }
  });

  // Logout event
  bot.on("logout", (user: { name: () => string }) => {
    runtime.log?.(`[${account.accountId}] WeChat logged out: ${user.name()}`);
    statusSink?.({ loggedIn: false });
  });

  // Message event — main pipeline
  bot.on("message", (msg: Message) => {
    if (stopped || abortSignal.aborted) {
      return;
    }
    processMessage(
      msg,
      bot,
      account,
      config,
      runtime,
      core,
      effectiveMediaMaxMb,
      statusSink,
    ).catch((err) => {
      runtime.error?.(`[${account.accountId}] WeChat message processing failed: ${String(err)}`);
    });
  });

  // Error event
  bot.on("error", (error: Error) => {
    runtime.error?.(`[${account.accountId}] WeChat bot error: ${error.message}`);
  });

  // Start the bot
  await bot.start();

  // Register abort signal handler
  abortSignal.addEventListener(
    "abort",
    () => {
      stop();
    },
    { once: true },
  );

  return { stop };
}
