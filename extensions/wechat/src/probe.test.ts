import { describe, expect, it, vi } from "vitest";
import { probeWeChat } from "./probe.js";

function createMockBot(overrides: Record<string, unknown> = {}) {
  return {
    logonoff: vi.fn(() => true),
    currentUser: {
      id: "wxid_test123",
      name: () => "TestBot",
    },
    puppet: { name: "padlocal" },
    ...overrides,
  };
}

describe("probeWeChat", () => {
  it("returns ok with user info when logged in", async () => {
    const bot = createMockBot();
    const result = await probeWeChat(bot as never);

    expect(result.ok).toBe(true);
    expect(result.user).toEqual({ id: "wxid_test123", name: "TestBot" });
    expect(result.puppet).toBe("padlocal");
    expect(result.elapsedMs).toBeGreaterThanOrEqual(0);
  });

  it("returns not ok when not logged in", async () => {
    const bot = createMockBot({ logonoff: vi.fn(() => false) });
    const result = await probeWeChat(bot as never);

    expect(result.ok).toBe(false);
    expect(result.error).toContain("Not logged in");
  });

  it("returns error when bot throws", async () => {
    const bot = createMockBot({
      logonoff: vi.fn(() => {
        throw new Error("Connection lost");
      }),
    });
    const result = await probeWeChat(bot as never);

    expect(result.ok).toBe(false);
    expect(result.error).toContain("Connection lost");
    expect(result.elapsedMs).toBeGreaterThanOrEqual(0);
  });

  it("handles missing currentUser gracefully", async () => {
    const bot = createMockBot({ currentUser: undefined });
    const result = await probeWeChat(bot as never);

    expect(result.ok).toBe(true);
    expect(result.user).toEqual({ id: "unknown", name: "unknown" });
  });

  it("handles missing puppet name", async () => {
    const bot = createMockBot({ puppet: {} });
    const result = await probeWeChat(bot as never);

    expect(result.ok).toBe(true);
    expect(result.puppet).toBe("unknown");
  });
});
