import type { OpenClawConfig } from "openclaw/plugin-sdk";
import { describe, expect, it } from "vitest";
import {
  listWeChatAccountIds,
  resolveDefaultWeChatAccountId,
  resolveWeChatAccount,
  listEnabledWeChatAccounts,
} from "./accounts.js";

describe("listWeChatAccountIds", () => {
  it("returns default when no accounts configured", () => {
    const cfg = { channels: { wechat: {} } } as unknown as OpenClawConfig;
    expect(listWeChatAccountIds(cfg)).toEqual(["default"]);
  });

  it("returns configured account ids sorted", () => {
    const cfg = {
      channels: {
        wechat: {
          accounts: {
            work: {},
            personal: {},
          },
        },
      },
    } as unknown as OpenClawConfig;
    expect(listWeChatAccountIds(cfg)).toEqual(["personal", "work"]);
  });

  it("returns default when channels.wechat is undefined", () => {
    const cfg = { channels: {} } as unknown as OpenClawConfig;
    expect(listWeChatAccountIds(cfg)).toEqual(["default"]);
  });
});

describe("resolveDefaultWeChatAccountId", () => {
  it("returns configured default", () => {
    const cfg = {
      channels: {
        wechat: {
          defaultAccount: "work",
          accounts: { work: {}, personal: {} },
        },
      },
    } as unknown as OpenClawConfig;
    expect(resolveDefaultWeChatAccountId(cfg)).toBe("work");
  });

  it("falls back to default when no defaultAccount set", () => {
    const cfg = { channels: { wechat: {} } } as unknown as OpenClawConfig;
    expect(resolveDefaultWeChatAccountId(cfg)).toBe("default");
  });
});

describe("resolveWeChatAccount", () => {
  it("resolves default account with base config", () => {
    const cfg = {
      channels: {
        wechat: {
          puppet: "padlocal",
          padlocalToken: "test_token",
          dmPolicy: "allowlist",
          allowFrom: ["wxid_abc"],
        },
      },
    } as unknown as OpenClawConfig;

    const account = resolveWeChatAccount({ cfg });
    expect(account.accountId).toBe("default");
    expect(account.puppet).toBe("padlocal");
    expect(account.padlocalToken).toBe("test_token");
    expect(account.tokenSource).toBe("config");
    expect(account.enabled).toBe(true);
    expect(account.config.dmPolicy).toBe("allowlist");
    expect(account.config.allowFrom).toEqual(["wxid_abc"]);
  });

  it("merges account config over base config", () => {
    const cfg = {
      channels: {
        wechat: {
          puppet: "padlocal",
          padlocalToken: "base_token",
          dmPolicy: "pairing",
          accounts: {
            work: {
              padlocalToken: "work_token",
              dmPolicy: "open",
            },
          },
        },
      },
    } as unknown as OpenClawConfig;

    const account = resolveWeChatAccount({ cfg, accountId: "work" });
    expect(account.accountId).toBe("work");
    expect(account.padlocalToken).toBe("work_token");
    expect(account.tokenSource).toBe("config");
    expect(account.config.dmPolicy).toBe("open");
  });

  it("defaults puppet to padlocal", () => {
    const cfg = {
      channels: {
        wechat: {},
      },
    } as unknown as OpenClawConfig;

    const account = resolveWeChatAccount({ cfg });
    expect(account.puppet).toBe("padlocal");
  });

  it("returns tokenSource none when no token", () => {
    const cfg = {
      channels: {
        wechat: {
          puppet: "wechat4u",
        },
      },
    } as unknown as OpenClawConfig;

    const account = resolveWeChatAccount({ cfg });
    expect(account.padlocalToken).toBe("");
    expect(account.tokenSource).toBe("none");
  });

  it("respects enabled=false", () => {
    const cfg = {
      channels: {
        wechat: {
          enabled: false,
        },
      },
    } as unknown as OpenClawConfig;

    const account = resolveWeChatAccount({ cfg });
    expect(account.enabled).toBe(false);
  });
});

describe("listEnabledWeChatAccounts", () => {
  it("filters disabled accounts", () => {
    const cfg = {
      channels: {
        wechat: {
          accounts: {
            enabled_one: { enabled: true },
            disabled_one: { enabled: false },
          },
        },
      },
    } as unknown as OpenClawConfig;

    const accounts = listEnabledWeChatAccounts(cfg);
    expect(accounts).toHaveLength(1);
    expect(accounts[0].accountId).toBe("enabled_one");
  });
});
