import type { Wechaty } from "wechaty";
import type { WeChatMomentsConfig } from "./types.js";

type CoreRuntime = {
  channel: {
    session: {
      injectContext?: (params: {
        sessionKey: string;
        text: string;
        label: string;
      }) => void;
    };
  };
};

/**
 * Start polling WeChat Moments feed.
 * Only available with padlocal puppet.
 *
 * Polls at the configured interval, formats new Moments posts,
 * and injects them as agent context.
 */
export function startMomentsPoller(
  bot: Wechaty,
  config: WeChatMomentsConfig,
  core: CoreRuntime,
): { stop: () => void } {
  const intervalSeconds = config.pollIntervalSeconds ?? 300;
  const maxPerPoll = config.maxPerPoll ?? 20;
  const injectAsContext = config.injectAsContext !== false;

  let lastPollTime = Date.now();
  let stopped = false;

  const poll = async () => {
    if (stopped) {
      return;
    }

    try {
      if (!bot.logonoff()) {
        return;
      }

      // padlocal puppet exposes getMoments — access via puppet directly
      const puppet = bot.puppet as {
        getMoments?: (params: { count: number }) => Promise<MomentEntry[]>;
      };

      if (typeof puppet.getMoments !== "function") {
        console.warn("[wechat] Moments polling requires padlocal puppet with getMoments support");
        return;
      }

      const moments = await puppet.getMoments({ count: maxPerPoll });

      for (const moment of moments) {
        const createTime = moment.createTime ?? 0;
        if (createTime * 1000 <= lastPollTime) {
          continue;
        }

        const formatted = formatMoment(moment);
        if (formatted && injectAsContext && core.channel.session.injectContext) {
          core.channel.session.injectContext({
            sessionKey: "wechat-moments",
            text: formatted,
            label: "wechat-moments",
          });
        }
      }

      lastPollTime = Date.now();
    } catch (err) {
      console.error("[wechat] Moments poll error:", err);
    }
  };

  const intervalId = setInterval(() => void poll(), intervalSeconds * 1000);

  // Initial poll after short delay
  setTimeout(() => void poll(), 5000);

  return {
    stop: () => {
      stopped = true;
      clearInterval(intervalId);
    },
  };
}

type MomentEntry = {
  userName?: string;
  createTime?: number;
  content?: string;
  imageCount?: number;
  likeCount?: number;
  comments?: Array<{ author?: string; content?: string }>;
};

function formatMoment(moment: MomentEntry): string | null {
  const name = moment.userName ?? "Unknown";
  const timeAgo = moment.createTime
    ? formatTimeAgo(moment.createTime * 1000)
    : "unknown time";
  const content = moment.content?.trim();

  if (!content) {
    return null;
  }

  const parts: string[] = [];
  parts.push(`[WeChat Moment — ${name}, ${timeAgo}]`);
  parts.push(content);

  const extras: string[] = [];
  if (moment.imageCount && moment.imageCount > 0) {
    extras.push(`${moment.imageCount} images`);
  }
  if (moment.likeCount && moment.likeCount > 0) {
    extras.push(`${moment.likeCount} likes`);
  }
  if (extras.length > 0) {
    parts.push(`[${extras.join("] [")}]`);
  }

  if (moment.comments && moment.comments.length > 0) {
    const topComments = moment.comments.slice(0, 2);
    const commentLines = topComments
      .map((c) => `${c.author ?? "?"}: ${c.content ?? ""}`)
      .join(", ");
    parts.push(`[Comments: ${commentLines}]`);
  }

  return parts.join("\n");
}

function formatTimeAgo(timestampMs: number): string {
  const diffMs = Date.now() - timestampMs;
  const diffMinutes = Math.floor(diffMs / 60000);
  if (diffMinutes < 1) {
    return "just now";
  }
  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  }
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}
