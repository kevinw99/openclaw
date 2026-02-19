import type { WeChatConfig } from "./types.js";

export type WeChatAllowlistMatch = {
  allowed: boolean;
  matchKey?: string;
  matchSource?: "wildcard" | "id";
};

export function resolveWeChatAllowlistMatch(params: {
  allowFrom: string[];
  senderId: string;
}): WeChatAllowlistMatch {
  const allowFrom = params.allowFrom
    .map((entry) => entry.trim().toLowerCase().replace(/^(wechat|wx):/i, ""))
    .filter(Boolean);

  if (allowFrom.length === 0) {
    return { allowed: false };
  }
  if (allowFrom.includes("*")) {
    return { allowed: true, matchKey: "*", matchSource: "wildcard" };
  }

  const senderId = params.senderId.toLowerCase();
  if (allowFrom.includes(senderId)) {
    return { allowed: true, matchKey: senderId, matchSource: "id" };
  }

  return { allowed: false };
}

export function isWeChatGroupAllowed(params: {
  groupPolicy: "allowlist" | "open" | "disabled";
  senderId: string;
}): boolean {
  const { groupPolicy } = params;
  if (groupPolicy === "disabled") {
    return false;
  }
  if (groupPolicy === "open") {
    return true;
  }
  // allowlist: groups require @mention, handled separately
  return true;
}

export function resolveWeChatReplyPolicy(params: {
  isDirectMessage: boolean;
  globalConfig?: WeChatConfig;
}): { requireMention: boolean } {
  if (params.isDirectMessage) {
    return { requireMention: false };
  }

  const requireMention = params.globalConfig?.requireMention ?? true;
  return { requireMention };
}
