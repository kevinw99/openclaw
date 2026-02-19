import type {
  ChannelOnboardingAdapter,
  ChannelOnboardingDmPolicy,
  OpenClawConfig,
  WizardPrompter,
} from "openclaw/plugin-sdk";
import {
  addWildcardAllowFrom,
  DEFAULT_ACCOUNT_ID,
  normalizeAccountId,
  promptAccountId,
} from "openclaw/plugin-sdk";
import {
  listWeChatAccountIds,
  resolveDefaultWeChatAccountId,
  resolveWeChatAccount,
} from "./accounts.js";

const channel = "wechat" as const;

function setWeChatDmPolicy(
  cfg: OpenClawConfig,
  dmPolicy: "pairing" | "allowlist" | "open" | "disabled",
) {
  const allowFrom =
    dmPolicy === "open" ? addWildcardAllowFrom(cfg.channels?.wechat?.allowFrom) : undefined;
  return {
    ...cfg,
    channels: {
      ...cfg.channels,
      wechat: {
        ...cfg.channels?.wechat,
        dmPolicy,
        ...(allowFrom ? { allowFrom } : {}),
      },
    },
  } as OpenClawConfig;
}

async function noteWeChatTokenHelp(prompter: WizardPrompter): Promise<void> {
  await prompter.note(
    [
      "WeChat requires a Wechaty puppet for login.",
      "",
      "Option 1 — PadLocal (recommended, paid):",
      "  Get a token from https://pad-local.com",
      "  Token looks like: puppet_padlocal_xxxxxxxxxxxxxxxx",
      "",
      "Option 2 — wechat4u (free, limited):",
      "  Uses web protocol, no token needed.",
      "  Note: WeChat may block web login for some accounts.",
      "",
      "Tip: you can also set WECHAT_PADLOCAL_TOKEN in your env.",
    ].join("\n"),
    "WeChat puppet setup",
  );
}

async function promptWeChatAllowFrom(params: {
  cfg: OpenClawConfig;
  prompter: WizardPrompter;
  accountId: string;
}): Promise<OpenClawConfig> {
  const { cfg, prompter, accountId } = params;
  const resolved = resolveWeChatAccount({ cfg, accountId });
  const existingAllowFrom = resolved.config.allowFrom ?? [];
  const entry = await prompter.text({
    message: "WeChat allowFrom (wxid)",
    placeholder: "wxid_xxxxxxxxxxxxx",
    initialValue: existingAllowFrom[0] ? String(existingAllowFrom[0]) : undefined,
    validate: (value) => {
      const raw = String(value ?? "").trim();
      if (!raw) {
        return "Required";
      }
      return undefined;
    },
  });
  const normalized = String(entry).trim();
  const merged = [
    ...existingAllowFrom.map((item) => String(item).trim()).filter(Boolean),
    normalized,
  ];
  const unique = [...new Set(merged)];

  if (accountId === DEFAULT_ACCOUNT_ID) {
    return {
      ...cfg,
      channels: {
        ...cfg.channels,
        wechat: {
          ...cfg.channels?.wechat,
          enabled: true,
          dmPolicy: "allowlist",
          allowFrom: unique,
        },
      },
    } as OpenClawConfig;
  }

  return {
    ...cfg,
    channels: {
      ...cfg.channels,
      wechat: {
        ...cfg.channels?.wechat,
        enabled: true,
        accounts: {
          ...cfg.channels?.wechat?.accounts,
          [accountId]: {
            ...cfg.channels?.wechat?.accounts?.[accountId],
            enabled: cfg.channels?.wechat?.accounts?.[accountId]?.enabled ?? true,
            dmPolicy: "allowlist",
            allowFrom: unique,
          },
        },
      },
    },
  } as OpenClawConfig;
}

const dmPolicy: ChannelOnboardingDmPolicy = {
  label: "WeChat",
  channel,
  policyKey: "channels.wechat.dmPolicy",
  allowFromKey: "channels.wechat.allowFrom",
  getCurrent: (cfg) => (cfg.channels?.wechat?.dmPolicy ?? "pairing") as "pairing",
  setPolicy: (cfg, policy) => setWeChatDmPolicy(cfg, policy),
  promptAllowFrom: async ({ cfg, prompter, accountId }) => {
    const id =
      accountId && normalizeAccountId(accountId)
        ? (normalizeAccountId(accountId) ?? DEFAULT_ACCOUNT_ID)
        : resolveDefaultWeChatAccountId(cfg);
    return promptWeChatAllowFrom({
      cfg: cfg,
      prompter,
      accountId: id,
    });
  },
};

export const wechatOnboardingAdapter: ChannelOnboardingAdapter = {
  channel,
  dmPolicy,
  getStatus: async ({ cfg }) => {
    const configured = listWeChatAccountIds(cfg).some((accountId) => {
      const account = resolveWeChatAccount({ cfg: cfg, accountId });
      // wechat4u puppet doesn't need a token
      return account.puppet === "wechat4u" || Boolean(account.padlocalToken);
    });
    return {
      channel,
      configured,
      statusLines: [`WeChat: ${configured ? "configured" : "needs setup"}`],
      selectionHint: configured ? "recommended · configured" : "requires Wechaty puppet",
      quickstartScore: configured ? 1 : 20,
    };
  },
  configure: async ({
    cfg,
    prompter,
    accountOverrides,
    shouldPromptAccountIds,
    forceAllowFrom,
  }) => {
    const wechatOverride = accountOverrides.wechat?.trim();
    const defaultWeChatAccountId = resolveDefaultWeChatAccountId(cfg);
    let wechatAccountId = wechatOverride
      ? normalizeAccountId(wechatOverride)
      : defaultWeChatAccountId;
    if (shouldPromptAccountIds && !wechatOverride) {
      wechatAccountId = await promptAccountId({
        cfg: cfg,
        prompter,
        label: "WeChat",
        currentId: wechatAccountId,
        listAccountIds: listWeChatAccountIds,
        defaultAccountId: defaultWeChatAccountId,
      });
    }

    let next = cfg;
    const resolvedAccount = resolveWeChatAccount({ cfg: next, accountId: wechatAccountId });
    const accountConfigured =
      resolvedAccount.puppet === "wechat4u" || Boolean(resolvedAccount.padlocalToken);
    const allowEnv = wechatAccountId === DEFAULT_ACCOUNT_ID;
    const canUseEnv = allowEnv && Boolean(process.env.WECHAT_PADLOCAL_TOKEN?.trim());
    const hasConfigToken = Boolean(resolvedAccount.config.padlocalToken);

    if (!accountConfigured) {
      await noteWeChatTokenHelp(prompter);
    }

    // Prompt for puppet type
    const puppetChoice = await prompter.select({
      message: "Puppet backend",
      options: [
        { value: "padlocal", label: "PadLocal (recommended, paid)" },
        { value: "wechat4u", label: "wechat4u (free, web protocol)" },
      ],
      initialValue: resolvedAccount.puppet ?? "padlocal",
    });

    let padlocalToken: string | null = null;

    if (puppetChoice === "padlocal") {
      if (canUseEnv && !resolvedAccount.config.padlocalToken) {
        const keepEnv = await prompter.confirm({
          message: "WECHAT_PADLOCAL_TOKEN detected. Use env var?",
          initialValue: true,
        });
        if (!keepEnv) {
          padlocalToken = String(
            await prompter.text({
              message: "Enter PadLocal token",
              validate: (value) => (value?.trim() ? undefined : "Required"),
            }),
          ).trim();
        }
      } else if (hasConfigToken) {
        const keep = await prompter.confirm({
          message: "PadLocal token already configured. Keep it?",
          initialValue: true,
        });
        if (!keep) {
          padlocalToken = String(
            await prompter.text({
              message: "Enter PadLocal token",
              validate: (value) => (value?.trim() ? undefined : "Required"),
            }),
          ).trim();
        }
      } else {
        padlocalToken = String(
          await prompter.text({
            message: "Enter PadLocal token",
            validate: (value) => (value?.trim() ? undefined : "Required"),
          }),
        ).trim();
      }
    }

    if (wechatAccountId === DEFAULT_ACCOUNT_ID) {
      next = {
        ...next,
        channels: {
          ...next.channels,
          wechat: {
            ...next.channels?.wechat,
            enabled: true,
            puppet: puppetChoice as "padlocal" | "wechat4u",
            ...(padlocalToken ? { padlocalToken } : {}),
          },
        },
      } as OpenClawConfig;
    } else {
      next = {
        ...next,
        channels: {
          ...next.channels,
          wechat: {
            ...next.channels?.wechat,
            enabled: true,
            accounts: {
              ...next.channels?.wechat?.accounts,
              [wechatAccountId]: {
                ...next.channels?.wechat?.accounts?.[wechatAccountId],
                enabled: true,
                puppet: puppetChoice as "padlocal" | "wechat4u",
                ...(padlocalToken ? { padlocalToken } : {}),
              },
            },
          },
        },
      } as OpenClawConfig;
    }

    if (forceAllowFrom) {
      next = await promptWeChatAllowFrom({
        cfg: next,
        prompter,
        accountId: wechatAccountId,
      });
    }

    return { cfg: next, accountId: wechatAccountId };
  },
};
