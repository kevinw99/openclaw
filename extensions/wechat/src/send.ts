import type { Wechaty } from "wechaty";
import { FileBox } from "file-box";
import type { WeChatSendResult } from "./types.js";
import { getBot } from "./client.js";
import { isGroupTarget } from "./targets.js";

export type SendWeChatMessageParams = {
  to: string;
  text: string;
  accountId?: string;
  mediaPath?: string;
  bot?: Wechaty;
};

function resolveBotInstance(params: SendWeChatMessageParams): Wechaty | null {
  if (params.bot) {
    return params.bot;
  }
  if (params.accountId) {
    return getBot(params.accountId) ?? null;
  }
  return null;
}

export async function sendWeChatMessage(
  params: SendWeChatMessageParams,
): Promise<WeChatSendResult> {
  const { to, text, mediaPath } = params;
  const bot = resolveBotInstance(params);
  if (!bot) {
    return { ok: false, error: "No WeChat bot instance available" };
  }

  if (!to?.trim()) {
    return { ok: false, error: "No recipient provided" };
  }

  try {
    if (isGroupTarget(to)) {
      const room = await bot.Room.find({ id: to });
      if (!room) {
        return { ok: false, error: `Room not found: ${to}` };
      }
      if (mediaPath) {
        await room.say(FileBox.fromFile(mediaPath));
      }
      if (text) {
        const chunks = chunkText(text, 2000);
        for (const chunk of chunks) {
          await room.say(chunk);
        }
      }
    } else {
      const contact = await bot.Contact.find({ id: to });
      if (!contact) {
        return { ok: false, error: `Contact not found: ${to}` };
      }
      if (mediaPath) {
        await contact.say(FileBox.fromFile(mediaPath));
      }
      if (text) {
        const chunks = chunkText(text, 2000);
        for (const chunk of chunks) {
          await contact.say(chunk);
        }
      }
    }
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export function chunkText(text: string, limit: number): string[] {
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
}
