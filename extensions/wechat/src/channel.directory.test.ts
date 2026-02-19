import type { OpenClawConfig } from "openclaw/plugin-sdk";
import { describe, expect, it } from "vitest";
import { wechatPlugin } from "./channel.js";

describe("wechat directory", () => {
  it("lists peers from contact index (empty when no bot running)", async () => {
    const cfg = {
      channels: {
        wechat: {
          allowFrom: ["wechat:wxid_abc123", "wx:wxid_def456", "wxid_ghi789"],
        },
      },
    } as unknown as OpenClawConfig;

    expect(wechatPlugin.directory).toBeTruthy();
    expect(wechatPlugin.directory?.listPeers).toBeTruthy();
    expect(wechatPlugin.directory?.listGroups).toBeTruthy();

    // With no bot running, listPeers falls back to contact index (empty)
    await expect(
      wechatPlugin.directory!.listPeers({
        cfg,
        accountId: undefined,
        query: undefined,
        limit: undefined,
      }),
    ).resolves.toEqual([]);

    // With no bot running, listGroups returns empty
    await expect(
      wechatPlugin.directory!.listGroups({
        cfg,
        accountId: undefined,
        query: undefined,
        limit: undefined,
      }),
    ).resolves.toEqual([]);
  });
});
