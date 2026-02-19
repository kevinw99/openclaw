import type { ChannelAccountSnapshot, ChannelStatusIssue } from "openclaw/plugin-sdk";

type WeChatAccountStatus = {
  accountId?: unknown;
  enabled?: unknown;
  configured?: unknown;
  dmPolicy?: unknown;
  puppet?: unknown;
  momentsEnabled?: unknown;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value && typeof value === "object");

const asString = (value: unknown): string | undefined =>
  typeof value === "string" ? value : typeof value === "number" ? String(value) : undefined;

function readWeChatAccountStatus(value: ChannelAccountSnapshot): WeChatAccountStatus | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    accountId: value.accountId,
    enabled: value.enabled,
    configured: value.configured,
    dmPolicy: value.dmPolicy,
    puppet: value.puppet,
    momentsEnabled: value.momentsEnabled,
  };
}

export function collectWeChatStatusIssues(
  accounts: ChannelAccountSnapshot[],
): ChannelStatusIssue[] {
  const issues: ChannelStatusIssue[] = [];
  for (const entry of accounts) {
    const account = readWeChatAccountStatus(entry);
    if (!account) {
      continue;
    }
    const accountId = asString(account.accountId) ?? "default";
    const enabled = account.enabled !== false;
    const configured = account.configured === true;
    if (!enabled || !configured) {
      continue;
    }

    if (account.dmPolicy === "open") {
      issues.push({
        channel: "wechat",
        accountId,
        kind: "config",
        message:
          'WeChat dmPolicy is "open", allowing any user to message the bot without pairing.',
        fix: 'Set channels.wechat.dmPolicy to "pairing" or "allowlist" to restrict access.',
      });
    }

    if (account.momentsEnabled === true && account.puppet !== "padlocal") {
      issues.push({
        channel: "wechat",
        accountId,
        kind: "config",
        message: "Moments polling is enabled but puppet is not padlocal. Moments require padlocal.",
        fix: 'Set channels.wechat.puppet to "padlocal" or disable moments.',
      });
    }
  }
  return issues;
}
