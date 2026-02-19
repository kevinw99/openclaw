import { describe, expect, it } from "vitest";
import { WeChatConfigSchema } from "./config-schema.js";

describe("WeChatConfigSchema", () => {
  it("accepts valid minimal config", () => {
    const result = WeChatConfigSchema.safeParse({
      puppet: "padlocal",
      padlocalToken: "puppet_padlocal_xxxxxxxxxxxxxxxx",
    });
    expect(result.success).toBe(true);
  });

  it("accepts valid full config", () => {
    const result = WeChatConfigSchema.safeParse({
      puppet: "padlocal",
      padlocalToken: "puppet_padlocal_xxxxxxxxxxxxxxxx",
      dmPolicy: "allowlist",
      allowFrom: ["wxid_abc123"],
      groupPolicy: "open",
      requireMention: true,
      voice: {
        transcribe: true,
        provider: "openai",
        openaiApiKey: "sk-test",
      },
      moments: {
        enabled: true,
        pollIntervalSeconds: 600,
        injectAsContext: true,
        maxPerPoll: 10,
      },
      contacts: {
        indexEnabled: true,
        refreshIntervalHours: 12,
      },
      minReplyDelayMs: 1000,
      mediaMaxMb: 25,
      ackReaction: {
        emoji: "eyes",
        direct: false,
        group: "mentions",
      },
    });
    expect(result.success).toBe(true);
  });

  it("accepts wechat4u puppet without token", () => {
    const result = WeChatConfigSchema.safeParse({
      puppet: "wechat4u",
    });
    expect(result.success).toBe(true);
  });

  it("accepts multi-account config", () => {
    const result = WeChatConfigSchema.safeParse({
      puppet: "padlocal",
      padlocalToken: "default_token",
      defaultAccount: "personal",
      accounts: {
        personal: {
          padlocalToken: "personal_token",
          dmPolicy: "pairing",
        },
        work: {
          puppet: "wechat4u",
          dmPolicy: "open",
        },
      },
    });
    expect(result.success).toBe(true);
  });

  it("rejects invalid puppet value", () => {
    const result = WeChatConfigSchema.safeParse({
      puppet: "invalid",
    });
    expect(result.success).toBe(false);
  });

  it("rejects invalid dmPolicy value", () => {
    const result = WeChatConfigSchema.safeParse({
      dmPolicy: "invalid",
    });
    expect(result.success).toBe(false);
  });

  it("rejects invalid groupPolicy value", () => {
    const result = WeChatConfigSchema.safeParse({
      groupPolicy: "invalid",
    });
    expect(result.success).toBe(false);
  });

  it("rejects invalid voice provider", () => {
    const result = WeChatConfigSchema.safeParse({
      voice: { provider: "invalid" },
    });
    expect(result.success).toBe(false);
  });

  it("rejects invalid ack reaction group mode", () => {
    const result = WeChatConfigSchema.safeParse({
      ackReaction: { group: "invalid" },
    });
    expect(result.success).toBe(false);
  });

  it("accepts empty config", () => {
    const result = WeChatConfigSchema.safeParse({});
    expect(result.success).toBe(true);
  });
});
