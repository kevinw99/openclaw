import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { startMomentsPoller } from "./moments.js";

function createMockBot(loggedIn = true, moments: unknown[] = []) {
  return {
    logonoff: vi.fn(() => loggedIn),
    puppet: {
      getMoments: vi.fn().mockResolvedValue(moments),
    },
  };
}

function createMockCore() {
  return {
    channel: {
      session: {
        injectContext: vi.fn(),
      },
    },
  };
}

describe("startMomentsPoller", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("polls after initial delay", async () => {
    const bot = createMockBot(true, []);
    const core = createMockCore();

    const poller = startMomentsPoller(bot as never, { pollIntervalSeconds: 60 }, core);

    // Advance past the initial 5s delay
    await vi.advanceTimersByTimeAsync(5000);

    expect(bot.puppet.getMoments).toHaveBeenCalledTimes(1);
    poller.stop();
  });

  it("polls at configured interval", async () => {
    const bot = createMockBot(true, []);
    const core = createMockCore();

    const poller = startMomentsPoller(bot as never, { pollIntervalSeconds: 10 }, core);

    // Initial poll at 5s
    await vi.advanceTimersByTimeAsync(5000);
    expect(bot.puppet.getMoments).toHaveBeenCalledTimes(1);

    // Interval poll at 10s
    await vi.advanceTimersByTimeAsync(10000);
    expect(bot.puppet.getMoments).toHaveBeenCalledTimes(2);

    poller.stop();
  });

  it("skips poll when bot is not logged in", async () => {
    const bot = createMockBot(false, []);
    const core = createMockCore();

    const poller = startMomentsPoller(bot as never, { pollIntervalSeconds: 60 }, core);

    await vi.advanceTimersByTimeAsync(5000);

    expect(bot.puppet.getMoments).not.toHaveBeenCalled();
    poller.stop();
  });

  it("skips when puppet lacks getMoments", async () => {
    const bot = {
      logonoff: vi.fn(() => true),
      puppet: {},
    };
    const core = createMockCore();

    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const poller = startMomentsPoller(bot as never, { pollIntervalSeconds: 60 }, core);

    await vi.advanceTimersByTimeAsync(5000);

    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("getMoments"));
    poller.stop();
    warnSpy.mockRestore();
  });

  it("injects new moments as context", async () => {
    const now = Date.now();
    const moments = [
      {
        userName: "Alice",
        createTime: Math.floor(now / 1000) + 10, // future = newer than lastPollTime
        content: "Beautiful sunset today",
        imageCount: 3,
        likeCount: 12,
        comments: [{ author: "Bob", content: "Amazing!" }],
      },
    ];
    const bot = createMockBot(true, moments);
    const core = createMockCore();

    const poller = startMomentsPoller(
      bot as never,
      { pollIntervalSeconds: 60, injectAsContext: true },
      core,
    );

    await vi.advanceTimersByTimeAsync(5000);

    expect(core.channel.session.injectContext).toHaveBeenCalledWith(
      expect.objectContaining({
        sessionKey: "wechat-moments",
        label: "wechat-moments",
        text: expect.stringContaining("Alice"),
      }),
    );
    poller.stop();
  });

  it("deduplicates moments older than last poll", async () => {
    const oldMoment = {
      userName: "Alice",
      createTime: Math.floor(Date.now() / 1000) - 600, // 10 minutes ago
      content: "Old post",
    };
    const bot = createMockBot(true, [oldMoment]);
    const core = createMockCore();

    const poller = startMomentsPoller(bot as never, { pollIntervalSeconds: 60 }, core);

    await vi.advanceTimersByTimeAsync(5000);

    expect(core.channel.session.injectContext).not.toHaveBeenCalled();
    poller.stop();
  });

  it("skips moments with empty content", async () => {
    const moments = [
      {
        userName: "Alice",
        createTime: Math.floor(Date.now() / 1000) + 10,
        content: "",
      },
    ];
    const bot = createMockBot(true, moments);
    const core = createMockCore();

    const poller = startMomentsPoller(bot as never, { pollIntervalSeconds: 60 }, core);

    await vi.advanceTimersByTimeAsync(5000);

    expect(core.channel.session.injectContext).not.toHaveBeenCalled();
    poller.stop();
  });

  it("stops cleanly", async () => {
    const bot = createMockBot(true, []);
    const core = createMockCore();

    const poller = startMomentsPoller(bot as never, { pollIntervalSeconds: 10 }, core);
    poller.stop();

    await vi.advanceTimersByTimeAsync(15000);

    // Should only have the initial setTimeout poll (which was stopped)
    expect(bot.puppet.getMoments).toHaveBeenCalledTimes(0);
  });

  it("uses default config values", async () => {
    const bot = createMockBot(true, []);
    const core = createMockCore();

    const poller = startMomentsPoller(bot as never, {}, core);

    // Default pollIntervalSeconds is 300 (5 minutes)
    await vi.advanceTimersByTimeAsync(5000); // initial delay
    expect(bot.puppet.getMoments).toHaveBeenCalledTimes(1);

    // Should not have polled again after only 60s
    await vi.advanceTimersByTimeAsync(60000);
    expect(bot.puppet.getMoments).toHaveBeenCalledTimes(1);

    poller.stop();
  });
});
