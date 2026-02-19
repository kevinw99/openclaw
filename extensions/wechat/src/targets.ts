export function normalizeWeChatTarget(raw: string): string | undefined {
  const trimmed = raw?.trim();
  if (!trimmed) {
    return undefined;
  }
  return trimmed.replace(/^(wechat|wx):/i, "");
}

export function looksLikeWeChatId(raw: string): boolean {
  const trimmed = raw.trim();
  if (!trimmed) {
    return false;
  }
  // wxid format or room id format
  return /^wxid_/.test(trimmed) || trimmed.includes("@chatroom");
}

export function isGroupTarget(to: string): boolean {
  return to.includes("@chatroom") || to.startsWith("@@");
}
