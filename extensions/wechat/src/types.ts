import type {
  WeChatConfigSchema,
  WeChatAccountConfigSchema,
  VoiceConfigSchema,
  MomentsConfigSchema,
  ContactsConfigSchema,
  AckReactionConfigSchema,
  z,
} from "./config-schema.js";

export type WeChatConfig = z.infer<typeof WeChatConfigSchema>;
export type WeChatAccountConfig = z.infer<typeof WeChatAccountConfigSchema>;
export type WeChatVoiceConfig = z.infer<typeof VoiceConfigSchema>;
export type WeChatMomentsConfig = z.infer<typeof MomentsConfigSchema>;
export type WeChatContactsConfig = z.infer<typeof ContactsConfigSchema>;
export type WeChatAckReactionConfig = z.infer<typeof AckReactionConfigSchema>;

export type WeChatTokenSource = "env" | "config" | "none";

export type ResolvedWeChatAccount = {
  accountId: string;
  enabled: boolean;
  configured: boolean;
  name?: string;
  puppet: "padlocal" | "wechat4u";
  padlocalToken: string;
  tokenSource: WeChatTokenSource;
  config: WeChatAccountConfig;
};

export type WeChatMessageContext = {
  chatId: string;
  messageId: string;
  senderId: string;
  senderName?: string;
  isGroup: boolean;
  mentionedBot: boolean;
  content: string;
  contentType: string;
  mediaPath?: string;
  mediaType?: string;
};

export type WeChatSendResult = {
  ok: boolean;
  error?: string;
};

export type WeChatProbeResult = {
  ok: boolean;
  user?: { id: string; name: string };
  puppet?: string;
  error?: string;
  elapsedMs: number;
};

export type WeChatMediaInfo = {
  path: string;
  contentType?: string;
  placeholder: string;
};
