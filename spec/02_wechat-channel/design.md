# Design: WeChat Channel Extension

## Overview

The WeChat extension is a native OpenClaw channel plugin (`extensions/wechat/`) that follows the same plugin architecture as the existing Zalo extension — with one key structural difference: instead of polling a REST API or receiving webhooks, the extension wraps a **Wechaty bot instance** that maintains a persistent connection to WeChat using an underlying puppet.

The extension registers a `ChannelPlugin` and `ChannelDock`, manages one Wechaty bot per configured account, and routes inbound messages through the standard OpenClaw pipeline (DM policy → pairing → routing → session recording → LLM dispatch → reply delivery).

WeChat-specific capabilities (voice transcription, Moments, contact graph) are implemented as background services that feed into agent context rather than as message channels.

---

## Architecture

### System Context

```
                              User's WeChat App
                                     │
                             (QR scan to link)
                                     │
                    ┌────────────────▼────────────────┐
                    │         WeChat Servers          │
                    │      (Tencent infrastructure)   │
                    └────────────────┬────────────────┘
                                     │  Puppet protocol
                         ┌───────────▼───────────┐
                         │  Wechaty Puppet Layer  │
                         │  padlocal (iPad proto) │
                         │  or wechat4u (web)     │
                         └───────────┬───────────┘
                                     │  events: message, login, scan, ...
                    ┌────────────────▼────────────────┐
                    │      extensions/wechat/          │
                    │                                  │
                    │  bot.ts       — bot lifecycle     │
                    │  monitor.ts   — event dispatch    │
                    │  send.ts      — outbound delivery │
                    │  moments.ts   — Moments polling   │
                    │  voice.ts     — transcription     │
                    │  contact-graph.ts — index         │
                    └────────────────┬────────────────┘
                                     │  PluginRuntime API
                    ┌────────────────▼────────────────┐
                    │       OpenClaw Gateway           │
                    │   ┌──────────────────────────┐  │
                    │   │  DM policy / pairing     │  │
                    │   │  Routing / session store  │  │
                    │   │  LLM dispatch            │  │
                    │   │  Reply pipeline          │  │
                    │   └──────────────────────────┘  │
                    └─────────────────────────────────┘
```

### Extension File Structure

```
extensions/wechat/
├── openclaw.plugin.json        # Manifest: id="wechat", channels=["wechat"]
├── package.json                # wechaty, wechaty-puppet-padlocal, wechaty-puppet-wechat4u
├── index.ts                    # Plugin entry: register channel + http handler (QR endpoint)
└── src/
    ├── config-schema.ts        # Zod schema for channels.wechat.* config section
    ├── accounts.ts             # Resolve account config from openclaw.json
    ├── channel.ts              # ChannelPlugin + ChannelDock definition
    ├── runtime.ts              # PluginRuntime singleton (same pattern as Zalo)
    ├── bot.ts                  # Wechaty bot factory + lifecycle management
    ├── monitor.ts              # Event dispatcher: bot.on() → processMessage pipeline
    ├── send.ts                 # Outbound: contact.say() / room.say()
    ├── actions.ts              # Tool actions: react, forward
    ├── onboarding.ts           # QR login flow adapter for openclaw channels login
    ├── probe.ts                # Health check: bot.logonoff() + currentUser
    ├── status-issues.ts        # Connectivity issue detection
    ├── types.ts                # WeChatAccount, WeChatMessage, resolved types
    ├── voice.ts                # Voice message → text transcription
    ├── moments.ts              # Moments feed polling (padlocal only)
    └── contact-graph.ts        # Contact index build + search tool
```

---

## Component Design

### 1. `config-schema.ts` — Configuration Shape

```typescript
// Zod schema for channels.wechat in openclaw.json
{
  channels: {
    wechat: {
      // Puppet selection
      puppet: "padlocal" | "wechat4u",  // default: "padlocal"
      padlocalToken: string,             // required if puppet="padlocal"

      // Access control (same pattern as other channels)
      dmPolicy: "pairing" | "allowlist" | "open" | "disabled",  // default: "pairing"
      allowFrom: string[],               // wxid values, e.g. ["wechat:wxid_xxx"]
      groupPolicy: "allowlist" | "open" | "disabled",           // default: "allowlist"
      requireMention: boolean,           // default: true

      // WeChat-specific features
      voice: {
        transcribe: boolean,             // default: true
        provider: "system" | "openai",  // default: "system" (macOS Speech)
        openaiApiKey: string,            // required if provider="openai"
      },
      moments: {
        enabled: boolean,               // default: false; padlocal only
        pollIntervalSeconds: number,    // default: 300
        injectAsContext: boolean,       // default: true
        maxPerPoll: number,             // default: 20
      },
      contacts: {
        indexEnabled: boolean,          // default: true
        refreshIntervalHours: number,   // default: 24
      },

      // Rate limiting (safety)
      minReplyDelayMs: number,          // default: 500

      // Media
      mediaMaxMb: number,               // default: 50 (inbound), outbound capped at 5
      ackReaction: {
        emoji: string,                  // e.g. "👀" — empty = disabled
        direct: boolean,               // default: false
        group: "always" | "mentions" | "never",  // default: "mentions"
      },

      // Multi-account
      accounts: {
        [accountId: string]: {
          // any of the above fields as per-account overrides
        }
      }
    }
  }
}
```

### 2. `bot.ts` — Wechaty Bot Lifecycle

One Wechaty instance per account. The factory function selects puppet based on config.

```typescript
import { WechatyBuilder } from 'wechaty'
import { PuppetPadlocal } from 'wechaty-puppet-padlocal'
import { PuppetWechat4u } from 'wechaty-puppet-wechat4u'

export function createWechatyBot(account: ResolvedWeChatAccount): Wechaty {
  const puppet = account.puppet === 'padlocal'
    ? new PuppetPadlocal({ token: account.padlocalToken })
    : new PuppetWechat4u()

  return WechatyBuilder.build({
    name: `openclaw-wechat-${account.accountId}`,  // → session file name
    puppet,
  })
}
// Session file auto-located by Wechaty at: ./${name}.memory-card.json
// We symlink / configure to: ~/.openclaw/credentials/wechat/<accountId>/session.json
```

### 3. `monitor.ts` — Message Event Dispatch

Wechaty is event-driven; no polling loop needed. The `startAccount` hook in `channel.ts` starts the bot and registers handlers:

```
bot.on('scan',     ...) → handleQrScan   — emit QR to terminal / HTTP endpoint
bot.on('login',    ...) → handleLogin    — log, update status, start Moments poller
bot.on('logout',   ...) → handleLogout   — log, update status, stop Moments poller
bot.on('message',  ...) → processMessage — main pipeline (see below)
bot.on('friendship',...) → handleFriendship — log friend requests
bot.on('error',    ...) → handleError    — log, update status
```

#### `processMessage` Pipeline

```
msg.self() = true → skip (own outbound messages)
msg.age() > 60s   → skip (stale messages from before bot started)

msg.type() dispatch:
  Text      → processTextOrCommand()
  Audio     → voice.transcribe() → processTextOrCommand("[Voice: <text>]")
  Image     → media.save() → processWithMedia()
  Video     → media.save() → processWithMedia()
  Recalled  → log("[Message recalled]"), skip
  Contact   → processTextOrCommand("<contact: Name (wxid)>")
  Url       → processTextOrCommand("<link: title — url>")
  Emoticon  → skip (sticker)
  Unknown   → skip

processTextOrCommand(text):
  room = await msg.room()           → isGroup = room !== null
  from = msg.from()                 → senderId, senderName = await from.name()

  if isGroup:
    chatId    = room.id
    chatLabel = await room.topic()
    if requireMention && !(await msg.mentionSelf()) → skip
  else:
    chatId    = from.id

  → dmPolicy check  (same logic as Zalo monitor.ts)
  → pairing check   (unknown sender → send pairing code via contact.say())
  → ackReaction     (optional emoji react before processing)
  → core.channel.routing.resolveAgentRoute(...)
  → core.channel.reply.formatAgentEnvelope({
       channel: "WeChat",
       from: senderName,
       timestamp: msg.date(),
       body: text,
     })
  → core.channel.session.recordInboundSession(...)
  → core.channel.reply.dispatchReplyWithBufferedBlockDispatcher({
       deliver: send.ts → contact.say(text) or room.say(text)
     })
```

### 4. `send.ts` — Outbound Delivery

Unlike Zalo (REST call), WeChat send is via the live bot instance:

```typescript
export async function sendWeChatMessage(params: {
  to: string          // wxid for DM, room.id for group
  text?: string
  mediaPath?: string
  bot: Wechaty
}): Promise<{ ok: boolean; error?: string }> {
  const isGroup = params.to.includes('@chatroom') || params.to.startsWith('@@')

  try {
    if (isGroup) {
      const room = await params.bot.Room.find({ id: params.to })
      if (!room) throw new Error(`Room not found: ${params.to}`)
      if (params.mediaPath) {
        await room.say(FileBox.fromFile(params.mediaPath))
      }
      if (params.text) await room.say(params.text)
    } else {
      const contact = await params.bot.Contact.find({ id: params.to })
      if (!contact) throw new Error(`Contact not found: ${params.to}`)
      if (params.mediaPath) {
        await contact.say(FileBox.fromFile(params.mediaPath))
      }
      if (params.text) await contact.say(params.text)
    }
    return { ok: true }
  } catch (err) {
    return { ok: false, error: String(err) }
  }
}
```

### 5. `voice.ts` — Voice Transcription

```
msg.type() === MessageType.Audio
  → fileBox = await msg.toFileBox()
  → filePath = save to temp file (.silk or .mp3 depending on puppet)
  → if provider === "openai":
       audioFile = convert .silk → .mp3 (ffmpeg)
       transcript = await openai.audio.transcriptions.create({ file, model: "whisper-1" })
  → if provider === "system":
       (macOS only) use NSSpeechRecognizer or shell: `swift transcribe.swift <path>`
  → result: "[Voice: <transcript>]"  or  "[Voice message — transcription unavailable]"
```

Note: WeChat uses SILK audio codec. Conversion to MP3 via ffmpeg is required for Whisper. The `system` provider calls macOS Speech.framework — requires macOS and the Swabble helper can be reused here.

### 6. `moments.ts` — Moments Feed Polling

Only available with padlocal puppet. Runs as a background interval after login:

```
every pollIntervalSeconds:
  moments = await (bot.puppet as PadLocalPuppet).getMoments({ count: maxPerPoll })
  for moment of moments where moment.createTime > lastPollTime:
    formatted = format(moment):
      "[WeChat Moment — <Name>, <time ago>]"
      "<text content>"
      "[<N> images] [<L> likes]"
      "[Comments: <author>: <text>, ...]"  (top 2)

    if injectAsContext:
      core.channel.session.injectContext({
        sessionKey: mainSessionKey,
        text: formatted,
        label: "wechat-moments",
      })

lastPollTime = now
```

### 7. `contact-graph.ts` — Contact Index

Built on login; refreshed periodically:

```typescript
type ContactNode = {
  wxid: string
  displayName: string      // WeChat name
  remark: string           // user's custom remark (备注)
  tags: string[]           // user-assigned tags
  sharedGroupIds: string[] // room IDs shared with user
  sharedGroupNames: string[]
  lastMessageAt?: Date     // from session history
}

// Persisted to: ~/.openclaw/credentials/wechat/<accountId>/contacts.json
// Exposed as agent tool: wechat_contacts({ query: string }) → ContactNode[]
```

---

## Data Flows

### Inbound Message Flow

```
WeChat → Puppet → Wechaty bot.on('message')
  → monitor.ts processMessage()
    → type dispatch (text / audio / image / ...)
    → [voice.ts] transcribe if Audio
    → [media] save if Image/Video
    → dmPolicy / pairing check
    → formatAgentEnvelope()
    → recordInboundSession()
    → dispatchReplyWithBufferedBlockDispatcher()
      → LLM processes message
      → deliver() → send.ts → contact.say() / room.say()
```

### Moments Context Flow

```
[background] moments.ts poll every N seconds
  → padlocal getMoments()
  → format new moments as structured text
  → injectContext() into agent's main session
    → next LLM interaction includes recent Moments as context
```

### Login Flow

```
openclaw channels login --channel wechat
  → channel.ts startAccount()
  → bot.ts createWechatyBot()
  → bot.start()
  → bot.on('scan') → print QR to terminal
  → user scans with WeChat app
  → bot.on('login') → session saved to credentials/wechat/<accountId>/
  → gateway ready to receive messages
```

---

## Approach Comparison

### Approach A: Wechaty (Chosen)
- **Pros**: TypeScript native, event-driven, multi-puppet, community-maintained, direct integration with OpenClaw's Node.js runtime
- **Cons**: padlocal requires paid token; account ban risk; WeChat web accounts blocked

### Approach B: wxauto (Python bridge)
- **Pros**: Free, reads Moments via UI automation
- **Cons**: Windows-only, Python runtime required, brittle UI scraping, incompatible with OpenClaw's architecture

### Approach C: Protocol reverse engineering
- **Pros**: Full control
- **Cons**: Very high ban risk, enormous engineering effort, legally risky, maintenance burden

**Decision**: Approach A — Wechaty. Consistent with OpenClaw's TypeScript runtime, proven track record with WeChat bots, pluggable puppet layer allows future switching.

---

## Technology Stack

- **Runtime**: Node.js 22+ (OpenClaw requirement)
- **Language**: TypeScript (strict mode)
- **Primary library**: Wechaty ^1.x
- **Primary puppet**: wechaty-puppet-padlocal (paid)
- **Dev puppet**: wechaty-puppet-wechat4u (free, web protocol)
- **Audio conversion**: ffmpeg (system dependency, for Whisper path)
- **Voice (cloud)**: OpenAI Whisper API
- **Voice (local)**: macOS Speech.framework via Swabble helper

---

## Configuration Example

```json5
// ~/.openclaw/openclaw.json
{
  channels: {
    wechat: {
      puppet: "padlocal",
      padlocalToken: "puppet_padlocal_xxxxxxxxxxxxxxxx",
      dmPolicy: "allowlist",
      allowFrom: ["wechat:wxid_yourown123"],
      groupPolicy: "allowlist",
      requireMention: true,
      voice: {
        transcribe: true,
        provider: "system",
      },
      moments: {
        enabled: true,
        pollIntervalSeconds: 300,
        injectAsContext: true,
      },
      contacts: {
        indexEnabled: true,
        refreshIntervalHours: 24,
      },
      minReplyDelayMs: 500,
      ackReaction: {
        emoji: "👀",
        direct: false,
        group: "mentions",
      },
    },
  },
}
```

---

## Security Considerations

- padlocal token stored in `openclaw.json` — file should have `600` permissions
- No message content sent outside configured LLM provider
- Voice: if `provider="openai"`, audio sent to OpenAI; must be explicit opt-in
- Contact index is local only; never sent to external services
- Rate limiting on outbound to reduce spam detection risk
- Session credential files: `~/.openclaw/credentials/wechat/` — local, not synced

---

## Testing Strategy

- **Unit tests**: message type dispatch, voice handler, contact indexer (mock puppet)
- **Integration tests**: loopback test with `wechaty-puppet-mock`
- **Manual tests**: full flow on padlocal dev token
- **No automated tests against real WeChat** (risk of account action)

---

## References

- `[ref-zalo-monitor]` /Users/kweng/AI/openclaw/extensions/zalo/src/monitor.ts — reference for processMessage pipeline
- `[ref-zalo-channel]` /Users/kweng/AI/openclaw/extensions/zalo/src/channel.ts — reference for ChannelPlugin structure
- `[ref-wechaty-api]` https://wechaty.js.org/docs/api/wechaty
- `[ref-wechaty-message]` https://wechaty.js.org/docs/api/message
- `[ref-padlocal]` https://github.com/wechaty/puppet-padlocal

---

**Last Updated**: 2026-02-19
