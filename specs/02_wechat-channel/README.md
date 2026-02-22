# WeChat Channel Extension for OpenClaw

> A native OpenClaw channel extension that connects WeChat personal accounts — including DMs, group chats, voice messages, and Moments — to the OpenClaw agent pipeline.

## Quick Links

- [Requirements](./requirements.md)
- [Design](./design.md)
- [Tasks](./tasks.md)
- [Status](./status.md)

## Status: BLOCKED — PadLocal is dead

> **2026-02**: PadLocal (the primary Wechaty puppet) is confirmed dead — npm unpublished 3+ years, website down, maintainer unresponsive, WeChat protocol changes broke login. This spec's implementation is complete but cannot proceed to integration testing. See [Spec 04](../04_wechat-continuous-sync/) for the replacement approach.

## Summary

OpenClaw has no WeChat support today. This spec defines a TypeScript channel extension (`extensions/wechat/`) that brings WeChat personal accounts into the OpenClaw ecosystem using [Wechaty](https://wechaty.js.org/) as the underlying puppet layer. The extension follows the same plugin pattern used by the existing Zalo and WhatsApp channels, and adds WeChat-specific capabilities: voice message transcription, Moments feed polling, and contact relationship indexing — all feeding into the spec 01 Full Context AI Personal Assistant.

## Key Decisions

- **Library**: Wechaty (Node.js/TypeScript) — consistent with OpenClaw's runtime, event-driven, supports multiple puppets
- **Puppet**: `padlocal` as primary (paid, most stable, supports Moments); `wechat4u` for dev/test only
- **Moments**: Polling via padlocal puppet API; injected as agent context, not as a message channel
- **Voice**: Auto-transcription using configurable provider (macOS Speech or OpenAI Whisper)
- **Auth**: QR scan via WeChat Linked Devices, session persisted to `~/.openclaw/credentials/wechat/<accountId>/`

## Scope

**In scope:**

- Direct messages (DMs) and group chat messages
- Voice message transcription
- Image / video / file receive and send
- Moments feed read (padlocal only)
- Contact graph indexing for relationship context
- Emoji reactions
- QR login, session persistence, multi-account support
- OpenClaw DM policy (pairing / allowlist / open / disabled)
- @mention gating in groups

**Out of scope (initial cut):**

- WeChat Official Accounts (public subscription accounts)
- WeChat Channels (视频号 short video)
- WeChat Work / WeCom (separate product, separate API)
- Mini Program interaction
- Posting to Moments (read-only initially)
- Red packet / payment features

## References

### Internal

- `[ref-zalo-ext]` /Users/kweng/AI/openclaw/extensions/zalo/ — reference implementation pattern
- `[ref-whatsapp-docs]` /Users/kweng/AI/openclaw/docs/channels/whatsapp.md — comparable channel doc
- `[ref-plugin-sdk]` openclaw/plugin-sdk — ChannelPlugin, ChannelDock, OpenClawPluginApi types
- `[ref-spec-01]` /Users/kweng/AI/openclaw/specs/01_full-context-ai-assistant/ — consumer of this channel

### External

- `[ref-wechaty]` https://wechaty.js.org/docs/wechaty
- `[ref-wechaty-message]` https://wechaty.js.org/docs/api/message
- `[ref-padlocal]` https://github.com/wechaty/puppet-padlocal
- `[ref-wechat4u]` https://github.com/wechaty/puppet-wechat4u

---

**Last Updated**: 2026-02-19
