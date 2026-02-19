import type { ChannelAccountSnapshot } from "openclaw/plugin-sdk";
import { describe, expect, it } from "vitest";
import { collectWeChatStatusIssues } from "./status-issues.js";

describe("collectWeChatStatusIssues", () => {
  it("returns no issues for properly configured account", () => {
    const accounts: ChannelAccountSnapshot[] = [
      {
        accountId: "default",
        enabled: true,
        configured: true,
        dmPolicy: "pairing",
        puppet: "padlocal",
      },
    ];
    expect(collectWeChatStatusIssues(accounts)).toEqual([]);
  });

  it("flags open dmPolicy", () => {
    const accounts: ChannelAccountSnapshot[] = [
      {
        accountId: "default",
        enabled: true,
        configured: true,
        dmPolicy: "open",
      },
    ];
    const issues = collectWeChatStatusIssues(accounts);
    expect(issues).toHaveLength(1);
    expect(issues[0].kind).toBe("config");
    expect(issues[0].message).toContain("open");
  });

  it("flags moments with non-padlocal puppet", () => {
    const accounts: ChannelAccountSnapshot[] = [
      {
        accountId: "default",
        enabled: true,
        configured: true,
        dmPolicy: "pairing",
        puppet: "wechat4u",
        momentsEnabled: true,
      },
    ];
    const issues = collectWeChatStatusIssues(accounts);
    expect(issues).toHaveLength(1);
    expect(issues[0].message).toContain("Moments");
  });

  it("skips disabled accounts", () => {
    const accounts: ChannelAccountSnapshot[] = [
      {
        accountId: "default",
        enabled: false,
        configured: true,
        dmPolicy: "open",
      },
    ];
    expect(collectWeChatStatusIssues(accounts)).toEqual([]);
  });

  it("skips unconfigured accounts", () => {
    const accounts: ChannelAccountSnapshot[] = [
      {
        accountId: "default",
        enabled: true,
        configured: false,
        dmPolicy: "open",
      },
    ];
    expect(collectWeChatStatusIssues(accounts)).toEqual([]);
  });

  it("reports multiple issues for one account", () => {
    const accounts: ChannelAccountSnapshot[] = [
      {
        accountId: "default",
        enabled: true,
        configured: true,
        dmPolicy: "open",
        puppet: "wechat4u",
        momentsEnabled: true,
      },
    ];
    const issues = collectWeChatStatusIssues(accounts);
    expect(issues).toHaveLength(2);
  });
});
