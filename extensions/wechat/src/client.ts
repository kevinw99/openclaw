import type { Wechaty } from "wechaty";
import { WechatyBuilder } from "wechaty";
import type { ResolvedWeChatAccount } from "./types.js";

const botCache = new Map<string, Wechaty>();

export function createWechatyBot(account: ResolvedWeChatAccount): Wechaty {
  const cached = botCache.get(account.accountId);
  if (cached) {
    return cached;
  }

  let puppetInstance: unknown;

  if (account.puppet === "padlocal") {
    // Dynamic import at call site — puppet packages are optional
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { PuppetPadlocal } = require("wechaty-puppet-padlocal") as {
      PuppetPadlocal: new (opts: { token: string }) => unknown;
    };
    puppetInstance = new PuppetPadlocal({ token: account.padlocalToken });
  } else {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { PuppetWechat4u } = require("wechaty-puppet-wechat4u") as {
      PuppetWechat4u: new () => unknown;
    };
    puppetInstance = new PuppetWechat4u();
  }

  const bot = WechatyBuilder.build({
    name: `openclaw-wechat-${account.accountId}`,
    puppet: puppetInstance as never,
  });

  botCache.set(account.accountId, bot);
  return bot;
}

export function getBot(accountId: string): Wechaty | undefined {
  return botCache.get(accountId);
}

export async function stopBot(accountId: string): Promise<void> {
  const bot = botCache.get(accountId);
  if (bot) {
    botCache.delete(accountId);
    try {
      await bot.stop();
    } catch {
      // ignore stop errors
    }
  }
}
