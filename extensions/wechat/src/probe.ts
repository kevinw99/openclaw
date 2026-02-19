import type { Wechaty } from "wechaty";

export type WeChatProbeResult = {
  ok: boolean;
  user?: { id: string; name: string };
  puppet?: string;
  error?: string;
  elapsedMs: number;
};

export async function probeWeChat(
  bot: Wechaty,
  timeoutMs = 5000,
): Promise<WeChatProbeResult> {
  const startTime = Date.now();

  try {
    const loggedIn = bot.logonoff();
    const elapsedMs = Date.now() - startTime;

    if (!loggedIn) {
      return { ok: false, error: "Not logged in", elapsedMs };
    }

    const currentUser = bot.currentUser;
    const name = currentUser?.name() ?? "unknown";
    const id = currentUser?.id ?? "unknown";

    return {
      ok: true,
      user: { id, name },
      puppet: String((bot.puppet as { name?: string })?.name ?? "unknown"),
      elapsedMs,
    };
  } catch (err) {
    const elapsedMs = Date.now() - startTime;
    if (err instanceof Error && err.name === "AbortError") {
      return { ok: false, error: `Request timed out after ${timeoutMs}ms`, elapsedMs };
    }
    return {
      ok: false,
      error: err instanceof Error ? err.message : String(err),
      elapsedMs,
    };
  }
}
