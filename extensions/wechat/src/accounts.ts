import type { ClawdbotConfig } from "openclaw/plugin-sdk";
import { DEFAULT_ACCOUNT_ID, normalizeAccountId } from "openclaw/plugin-sdk";
import type {
  ResolvedWeChatAccount,
  WeChatAccountConfig,
  WeChatConfig,
} from "./types.js";

export type { ResolvedWeChatAccount };

function listConfiguredAccountIds(cfg: ClawdbotConfig): string[] {
  const accounts = (cfg.channels?.wechat as WeChatConfig | undefined)?.accounts;
  if (!accounts || typeof accounts !== "object") {
    return [];
  }
  return Object.keys(accounts).filter(Boolean);
}

export function listWeChatAccountIds(cfg: ClawdbotConfig): string[] {
  const ids = listConfiguredAccountIds(cfg);
  if (ids.length === 0) {
    return [DEFAULT_ACCOUNT_ID];
  }
  return [...ids].toSorted((a, b) => a.localeCompare(b));
}

export function resolveDefaultWeChatAccountId(cfg: ClawdbotConfig): string {
  const wechatConfig = cfg.channels?.wechat as WeChatConfig | undefined;
  if (wechatConfig?.defaultAccount?.trim()) {
    return wechatConfig.defaultAccount.trim();
  }
  const ids = listWeChatAccountIds(cfg);
  if (ids.includes(DEFAULT_ACCOUNT_ID)) {
    return DEFAULT_ACCOUNT_ID;
  }
  return ids[0] ?? DEFAULT_ACCOUNT_ID;
}

function resolveAccountConfig(
  cfg: ClawdbotConfig,
  accountId: string,
): WeChatAccountConfig | undefined {
  const accounts = (cfg.channels?.wechat as WeChatConfig | undefined)?.accounts;
  if (!accounts || typeof accounts !== "object") {
    return undefined;
  }
  return accounts[accountId] as WeChatAccountConfig | undefined;
}

function mergeWeChatAccountConfig(cfg: ClawdbotConfig, accountId: string): WeChatAccountConfig {
  const raw = (cfg.channels?.wechat ?? {}) as WeChatConfig;
  const { accounts: _ignored, defaultAccount: _ignored2, ...base } = raw;
  const account = resolveAccountConfig(cfg, accountId) ?? {};
  return { ...base, ...account };
}

export function resolveWeChatToken(
  config: WeChatConfig | undefined,
  accountId?: string | null,
): { token: string; source: "env" | "config" | "none" } {
  const resolvedAccountId = accountId ?? DEFAULT_ACCOUNT_ID;
  const isDefaultAccount = resolvedAccountId === DEFAULT_ACCOUNT_ID;
  const baseConfig = config;
  const accountConfig =
    resolvedAccountId !== DEFAULT_ACCOUNT_ID
      ? (baseConfig?.accounts?.[resolvedAccountId] as WeChatConfig | undefined)
      : undefined;

  if (accountConfig) {
    const token = accountConfig.padlocalToken?.trim();
    if (token) {
      return { token, source: "config" };
    }
  }

  if (isDefaultAccount) {
    const token = baseConfig?.padlocalToken?.trim();
    if (token) {
      return { token, source: "config" };
    }
    const envToken = process.env.WECHAT_PADLOCAL_TOKEN?.trim();
    if (envToken) {
      return { token: envToken, source: "env" };
    }
  }

  return { token: "", source: "none" };
}

export function resolveWeChatAccount(params: {
  cfg: ClawdbotConfig;
  accountId?: string | null;
}): ResolvedWeChatAccount {
  const accountId = normalizeAccountId(params.accountId);
  const baseEnabled = (params.cfg.channels?.wechat as WeChatConfig | undefined)?.enabled !== false;
  const merged = mergeWeChatAccountConfig(params.cfg, accountId);
  const accountEnabled = merged.enabled !== false;
  const enabled = baseEnabled && accountEnabled;
  const tokenResolution = resolveWeChatToken(
    params.cfg.channels?.wechat as WeChatConfig | undefined,
    accountId,
  );
  const puppet = merged.puppet ?? "padlocal";
  const configured = puppet === "wechat4u" || Boolean(tokenResolution.token);

  return {
    accountId,
    name: merged.name?.trim() || undefined,
    enabled,
    configured,
    puppet,
    padlocalToken: tokenResolution.token,
    tokenSource: tokenResolution.source,
    config: merged,
  };
}

export function listEnabledWeChatAccounts(cfg: ClawdbotConfig): ResolvedWeChatAccount[] {
  return listWeChatAccountIds(cfg)
    .map((accountId) => resolveWeChatAccount({ cfg, accountId }))
    .filter((account) => account.enabled && account.configured);
}
