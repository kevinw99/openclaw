import type {
  ChannelAccountSnapshot,
  ChannelDock,
  ChannelPlugin,
  OpenClawConfig,
} from "openclaw/plugin-sdk";
import {
  applyAccountNameToChannelSection,
  buildChannelConfigSchema,
  DEFAULT_ACCOUNT_ID,
  deleteAccountFromConfigSection,
  formatPairingApproveHint,
  migrateBaseNameToDefaultAccount,
  normalizeAccountId,
  PAIRING_APPROVED_MESSAGE,
  setAccountEnabledInConfigSection,
} from "openclaw/plugin-sdk";
import {
  listWeChatAccountIds,
  resolveDefaultWeChatAccountId,
  resolveWeChatAccount,
  type ResolvedWeChatAccount,
} from "./accounts.js";
import { wechatMessageActions } from "./actions.js";
import { WeChatConfigSchema } from "./config-schema.js";
import { wechatOnboardingAdapter } from "./onboarding.js";
import { getBot } from "./bot.js";
import { probeWeChat } from "./probe.js";
import { sendWeChatMessage } from "./send.js";
import { collectWeChatStatusIssues } from "./status-issues.js";
import { searchContacts } from "./contact-graph.js";

const meta = {
  id: "wechat",
  label: "WeChat",
  selectionLabel: "WeChat (Personal)",
  docsPath: "/channels/wechat",
  docsLabel: "wechat",
  blurb: "WeChat personal account via Wechaty puppet layer.",
  aliases: ["wx"],
  order: 85,
  quickstartAllowFrom: true,
};

function normalizeWeChatMessagingTarget(raw: string): string | undefined {
  const trimmed = raw?.trim();
  if (!trimmed) {
    return undefined;
  }
  return trimmed.replace(/^(wechat|wx):/i, "");
}

export const wechatDock: ChannelDock = {
  id: "wechat",
  capabilities: {
    chatTypes: ["direct", "group"],
    media: true,
    blockStreaming: true,
  },
  outbound: { textChunkLimit: 2000 },
  config: {
    resolveAllowFrom: ({ cfg, accountId }) =>
      (resolveWeChatAccount({ cfg: cfg, accountId }).config.allowFrom ?? []).map((entry) =>
        String(entry),
      ),
    formatAllowFrom: ({ allowFrom }) =>
      allowFrom
        .map((entry) => String(entry).trim())
        .filter(Boolean)
        .map((entry) => entry.replace(/^(wechat|wx):/i, ""))
        .map((entry) => entry.toLowerCase()),
  },
  groups: {
    resolveRequireMention: ({ cfg, accountId }) => {
      const account = resolveWeChatAccount({ cfg, accountId });
      return account.config.requireMention !== false;
    },
  },
  threading: {
    resolveReplyToMode: () => "off",
  },
};

export const wechatPlugin: ChannelPlugin<ResolvedWeChatAccount> = {
  id: "wechat",
  meta,
  onboarding: wechatOnboardingAdapter,
  capabilities: {
    chatTypes: ["direct", "group"],
    media: true,
    reactions: false,
    threads: false,
    polls: false,
    nativeCommands: false,
    blockStreaming: true,
  },
  reload: { configPrefixes: ["channels.wechat"] },
  configSchema: buildChannelConfigSchema(WeChatConfigSchema),
  config: {
    listAccountIds: (cfg) => listWeChatAccountIds(cfg),
    resolveAccount: (cfg, accountId) => resolveWeChatAccount({ cfg: cfg, accountId }),
    defaultAccountId: (cfg) => resolveDefaultWeChatAccountId(cfg),
    setAccountEnabled: ({ cfg, accountId, enabled }) =>
      setAccountEnabledInConfigSection({
        cfg: cfg,
        sectionKey: "wechat",
        accountId,
        enabled,
        allowTopLevel: true,
      }),
    deleteAccount: ({ cfg, accountId }) =>
      deleteAccountFromConfigSection({
        cfg: cfg,
        sectionKey: "wechat",
        accountId,
        clearBaseFields: ["padlocalToken", "name"],
      }),
    isConfigured: (account) =>
      account.puppet === "wechat4u" || Boolean(account.padlocalToken?.trim()),
    describeAccount: (account): ChannelAccountSnapshot => ({
      accountId: account.accountId,
      name: account.name,
      enabled: account.enabled,
      configured: account.puppet === "wechat4u" || Boolean(account.padlocalToken?.trim()),
      tokenSource: account.tokenSource,
      puppet: account.puppet,
      momentsEnabled: account.config.moments?.enabled ?? false,
    }),
    resolveAllowFrom: ({ cfg, accountId }) =>
      (resolveWeChatAccount({ cfg: cfg, accountId }).config.allowFrom ?? []).map((entry) =>
        String(entry),
      ),
    formatAllowFrom: ({ allowFrom }) =>
      allowFrom
        .map((entry) => String(entry).trim())
        .filter(Boolean)
        .map((entry) => entry.replace(/^(wechat|wx):/i, ""))
        .map((entry) => entry.toLowerCase()),
  },
  security: {
    resolveDmPolicy: ({ cfg, accountId, account }) => {
      const resolvedAccountId = accountId ?? account.accountId ?? DEFAULT_ACCOUNT_ID;
      const useAccountPath = Boolean(cfg.channels?.wechat?.accounts?.[resolvedAccountId]);
      const basePath = useAccountPath
        ? `channels.wechat.accounts.${resolvedAccountId}.`
        : "channels.wechat.";
      return {
        policy: account.config.dmPolicy ?? "pairing",
        allowFrom: account.config.allowFrom ?? [],
        policyPath: `${basePath}dmPolicy`,
        allowFromPath: basePath,
        approveHint: formatPairingApproveHint("wechat"),
        normalizeEntry: (raw) => raw.replace(/^(wechat|wx):/i, ""),
      };
    },
  },
  groups: {
    resolveRequireMention: ({ cfg, accountId }) => {
      const account = resolveWeChatAccount({ cfg, accountId });
      return account.config.requireMention !== false;
    },
  },
  threading: {
    resolveReplyToMode: () => "off",
  },
  actions: wechatMessageActions,
  messaging: {
    normalizeTarget: normalizeWeChatMessagingTarget,
    targetResolver: {
      looksLikeId: (raw) => {
        const trimmed = raw.trim();
        if (!trimmed) {
          return false;
        }
        // wxid format or room id format
        return /^wxid_/.test(trimmed) || trimmed.includes("@chatroom");
      },
      hint: "<wxid or roomId>",
    },
  },
  directory: {
    self: async ({ cfg, accountId }) => {
      const bot = getBot(accountId ?? "default");
      if (!bot || !bot.logonoff()) {
        return null;
      }
      const user = bot.currentUser;
      return { kind: "user", id: user.id, name: user.name() };
    },
    listPeers: async ({ cfg, accountId, query, limit }) => {
      const effectiveAccountId = accountId ?? resolveDefaultWeChatAccountId(cfg);
      const contacts = searchContacts(query ?? "", effectiveAccountId);
      return contacts
        .slice(0, limit && limit > 0 ? limit : undefined)
        .map((c) => ({
          kind: "user" as const,
          id: c.wxid,
          name: c.displayName || c.remark || c.wxid,
        }));
    },
    listGroups: async ({ cfg, accountId }) => {
      const bot = getBot(accountId ?? "default");
      if (!bot || !bot.logonoff()) {
        return [];
      }
      try {
        const rooms = await bot.Room.findAll();
        const groups = [];
        for (const room of rooms.slice(0, 100)) {
          let topic = "";
          try {
            topic = (await room.topic()) || room.id;
          } catch {
            topic = room.id;
          }
          groups.push({ kind: "group" as const, id: room.id, name: topic });
        }
        return groups;
      } catch {
        return [];
      }
    },
  },
  setup: {
    resolveAccountId: ({ accountId }) => normalizeAccountId(accountId),
    applyAccountName: ({ cfg, accountId, name }) =>
      applyAccountNameToChannelSection({
        cfg: cfg,
        channelKey: "wechat",
        accountId,
        name,
      }),
    validateInput: ({ accountId, input }) => {
      if (input.useEnv && accountId !== DEFAULT_ACCOUNT_ID) {
        return "WECHAT_PADLOCAL_TOKEN can only be used for the default account.";
      }
      // wechat4u doesn't require a token
      if (!input.useEnv && !input.token && !input.puppet) {
        return "WeChat requires a padlocal token or wechat4u puppet selection.";
      }
      return null;
    },
    applyAccountConfig: ({ cfg, accountId, input }) => {
      const namedConfig = applyAccountNameToChannelSection({
        cfg: cfg,
        channelKey: "wechat",
        accountId,
        name: input.name,
      });
      const next =
        accountId !== DEFAULT_ACCOUNT_ID
          ? migrateBaseNameToDefaultAccount({
              cfg: namedConfig,
              channelKey: "wechat",
            })
          : namedConfig;
      if (accountId === DEFAULT_ACCOUNT_ID) {
        return {
          ...next,
          channels: {
            ...next.channels,
            wechat: {
              ...next.channels?.wechat,
              enabled: true,
              ...(input.useEnv
                ? {}
                : input.token
                  ? { padlocalToken: input.token }
                  : {}),
            },
          },
        } as OpenClawConfig;
      }
      return {
        ...next,
        channels: {
          ...next.channels,
          wechat: {
            ...next.channels?.wechat,
            enabled: true,
            accounts: {
              ...next.channels?.wechat?.accounts,
              [accountId]: {
                ...next.channels?.wechat?.accounts?.[accountId],
                enabled: true,
                ...(input.token ? { padlocalToken: input.token } : {}),
              },
            },
          },
        },
      } as OpenClawConfig;
    },
  },
  pairing: {
    idLabel: "wechatWxid",
    normalizeAllowEntry: (entry) => entry.replace(/^(wechat|wx):/i, ""),
    notifyApproval: async ({ cfg, id }) => {
      const account = resolveWeChatAccount({ cfg: cfg });
      const bot = getBot(account.accountId);
      if (!bot) {
        throw new Error("WeChat bot not running");
      }
      await sendWeChatMessage({ to: id, text: PAIRING_APPROVED_MESSAGE, bot });
    },
  },
  outbound: {
    deliveryMode: "direct",
    chunker: (text, limit) => {
      if (!text) {
        return [];
      }
      if (limit <= 0 || text.length <= limit) {
        return [text];
      }
      const chunks: string[] = [];
      let remaining = text;
      while (remaining.length > limit) {
        const window = remaining.slice(0, limit);
        const lastNewline = window.lastIndexOf("\n");
        const lastSpace = window.lastIndexOf(" ");
        let breakIdx = lastNewline > 0 ? lastNewline : lastSpace;
        if (breakIdx <= 0) {
          breakIdx = limit;
        }
        const rawChunk = remaining.slice(0, breakIdx);
        const chunk = rawChunk.trimEnd();
        if (chunk.length > 0) {
          chunks.push(chunk);
        }
        const brokeOnSeparator = breakIdx < remaining.length && /\s/.test(remaining[breakIdx]);
        const nextStart = Math.min(remaining.length, breakIdx + (brokeOnSeparator ? 1 : 0));
        remaining = remaining.slice(nextStart).trimStart();
      }
      if (remaining.length) {
        chunks.push(remaining);
      }
      return chunks;
    },
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
        text,
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
  },
  status: {
    defaultRuntime: {
      accountId: DEFAULT_ACCOUNT_ID,
      running: false,
      lastStartAt: null,
      lastStopAt: null,
      lastError: null,
    },
    collectStatusIssues: collectWeChatStatusIssues,
    buildChannelSummary: ({ snapshot }) => ({
      configured: snapshot.configured ?? false,
      tokenSource: snapshot.tokenSource ?? "none",
      puppet: snapshot.puppet ?? "padlocal",
      running: snapshot.running ?? false,
      loggedIn: snapshot.loggedIn ?? false,
      lastStartAt: snapshot.lastStartAt ?? null,
      lastStopAt: snapshot.lastStopAt ?? null,
      lastError: snapshot.lastError ?? null,
      probe: snapshot.probe,
      lastProbeAt: snapshot.lastProbeAt ?? null,
    }),
    probeAccount: async ({ account, timeoutMs }) => {
      const bot = getBot(account.accountId);
      if (!bot) {
        return { ok: false, error: "Bot not started", elapsedMs: 0 };
      }
      return probeWeChat(bot, timeoutMs);
    },
    buildAccountSnapshot: ({ account, runtime }) => {
      const configured =
        account.puppet === "wechat4u" || Boolean(account.padlocalToken?.trim());
      return {
        accountId: account.accountId,
        name: account.name,
        enabled: account.enabled,
        configured,
        tokenSource: account.tokenSource,
        puppet: account.puppet,
        momentsEnabled: account.config.moments?.enabled ?? false,
        running: runtime?.running ?? false,
        loggedIn: runtime?.loggedIn ?? false,
        lastStartAt: runtime?.lastStartAt ?? null,
        lastStopAt: runtime?.lastStopAt ?? null,
        lastError: runtime?.lastError ?? null,
        lastInboundAt: runtime?.lastInboundAt ?? null,
        lastOutboundAt: runtime?.lastOutboundAt ?? null,
        dmPolicy: account.config.dmPolicy ?? "pairing",
      };
    },
  },
  gateway: {
    startAccount: async (ctx) => {
      const account = ctx.account;
      ctx.log?.info(`[${account.accountId}] starting WeChat provider (puppet=${account.puppet})`);

      const { monitorWeChatProvider } = await import("./monitor.js");
      return monitorWeChatProvider({
        account,
        config: ctx.cfg,
        runtime: {
          log: (msg) => ctx.log?.info(msg),
          error: (msg) => ctx.log?.error(msg),
        },
        abortSignal: ctx.abortSignal,
        statusSink: (patch) => ctx.setStatus({ accountId: ctx.accountId, ...patch }),
      });
    },
  },
};
