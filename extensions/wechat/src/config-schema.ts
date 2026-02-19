import { z } from "zod";
export { z };

const VoiceProviderSchema = z.enum(["system", "openai"]);
const DmPolicySchema = z.enum(["pairing", "allowlist", "open", "disabled"]);
const GroupPolicySchema = z.enum(["allowlist", "open", "disabled"]);
const PuppetSchema = z.enum(["padlocal", "wechat4u"]);
const AckReactionGroupSchema = z.enum(["always", "mentions", "never"]);

const MarkdownConfigSchema = z
  .object({
    mode: z.enum(["native", "escape", "strip"]).optional(),
    tableMode: z.enum(["native", "ascii", "simple"]).optional(),
  })
  .strict()
  .optional();

export const VoiceConfigSchema = z
  .object({
    transcribe: z.boolean().optional(),
    provider: VoiceProviderSchema.optional(),
    openaiApiKey: z.string().optional(),
  })
  .strict();

export const MomentsConfigSchema = z
  .object({
    enabled: z.boolean().optional(),
    pollIntervalSeconds: z.number().int().positive().optional(),
    injectAsContext: z.boolean().optional(),
    maxPerPoll: z.number().int().positive().optional(),
  })
  .strict();

export const ContactsConfigSchema = z
  .object({
    indexEnabled: z.boolean().optional(),
    refreshIntervalHours: z.number().int().positive().optional(),
  })
  .strict();

export const AckReactionConfigSchema = z
  .object({
    emoji: z.string().optional(),
    direct: z.boolean().optional(),
    group: AckReactionGroupSchema.optional(),
  })
  .strict();

export const WeChatAccountConfigSchema = z
  .object({
    name: z.string().optional(),
    enabled: z.boolean().optional(),
    markdown: MarkdownConfigSchema,
    puppet: PuppetSchema.optional(),
    padlocalToken: z.string().optional(),
    dmPolicy: DmPolicySchema.optional(),
    allowFrom: z.array(z.string()).optional(),
    groupPolicy: GroupPolicySchema.optional(),
    requireMention: z.boolean().optional(),
    voice: VoiceConfigSchema.optional(),
    moments: MomentsConfigSchema.optional(),
    contacts: ContactsConfigSchema.optional(),
    minReplyDelayMs: z.number().int().min(0).optional(),
    mediaMaxMb: z.number().positive().optional(),
    ackReaction: AckReactionConfigSchema.optional(),
    responsePrefix: z.string().optional(),
  })
  .strict();

export const WeChatConfigSchema = z
  .object({
    enabled: z.boolean().optional(),
    name: z.string().optional(),
    markdown: MarkdownConfigSchema,
    puppet: PuppetSchema.optional().default("padlocal"),
    padlocalToken: z.string().optional(),
    dmPolicy: DmPolicySchema.optional().default("pairing"),
    allowFrom: z.array(z.string()).optional(),
    groupPolicy: GroupPolicySchema.optional().default("allowlist"),
    requireMention: z.boolean().optional().default(true),
    voice: VoiceConfigSchema.optional(),
    moments: MomentsConfigSchema.optional(),
    contacts: ContactsConfigSchema.optional(),
    minReplyDelayMs: z.number().int().min(0).optional(),
    mediaMaxMb: z.number().positive().optional(),
    ackReaction: AckReactionConfigSchema.optional(),
    responsePrefix: z.string().optional(),
    accounts: z.record(z.string(), WeChatAccountConfigSchema.optional()).optional(),
    defaultAccount: z.string().optional(),
  })
  .strict();
