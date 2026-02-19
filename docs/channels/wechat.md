---
summary: "WeChat - personal account DMs, groups, voice messages, and Moments via Wechaty puppet layer"
read_when:
  - user wants to connect WeChat personal account
  - user asks about WeChat setup or configuration
  - user needs help with WeChat channel
title: "WeChat"
---

# WeChat

Status: Personal account via Wechaty. Gateway owns the bot session. Supports DMs, groups, voice, media, and Moments.

## Quick setup

1. Install the extension: `openclaw extensions install @openclaw/wechat`
2. Get a PadLocal token from [pad-local.com](https://pad-local.com) (or use wechat4u for testing)
3. Run `openclaw channels setup --channel wechat`
4. Run `openclaw gateway start` — scan the QR code with your WeChat app
5. Send a DM to the linked account and complete pairing

Minimal config:

```json5
{
  channels: {
    wechat: {
      puppet: "padlocal",
      padlocalToken: "puppet_padlocal_xxxxxxxxxxxxxxxx",
      dmPolicy: "pairing"
    }
  }
}
```

## What it is

The WeChat extension wraps a [Wechaty](https://wechaty.js.org) bot instance that maintains a persistent connection to WeChat using an underlying puppet protocol. Unlike REST-based channels, WeChat is fully event-driven — the bot receives messages via `bot.on('message')` and sends replies via `contact.say()` / `room.say()`.

Two puppet backends are supported:

- **padlocal** (recommended): Uses the iPad protocol. Requires a paid token. Full feature support including Moments and stable connections.
- **wechat4u** (dev/test): Uses the web protocol. Free but limited — some accounts are blocked from web login, no Moments support.

## The account model

Each WeChat account corresponds to one personal WeChat login. The bot logs in by scanning a QR code — this links the personal WeChat account to the gateway session.

Multi-account is supported via the `accounts` config section:

```json5
{
  channels: {
    wechat: {
      puppet: "padlocal",
      padlocalToken: "token_for_default",
      accounts: {
        work: {
          padlocalToken: "token_for_work_account"
        }
      }
    }
  }
}
```

## Setup

### Fast path

```bash
openclaw channels setup --channel wechat
```

The wizard prompts for puppet type and token. For padlocal, you can also set the `WECHAT_PADLOCAL_TOKEN` environment variable.

### Manual config

Add to `~/.openclaw/openclaw.json`:

```json5
{
  channels: {
    wechat: {
      puppet: "padlocal",
      padlocalToken: "puppet_padlocal_xxxxxxxxxxxxxxxx"
    }
  }
}
```

### Login

Start the gateway and scan the QR code:

```bash
openclaw gateway start
```

The QR code prints to the terminal. Scan it with your WeChat app to link the account. The session persists across restarts.

## Access control

### DMs

Controlled by `dmPolicy` (default: `"pairing"`):

- **pairing**: Unknown senders get a one-time code. Approve with `openclaw channels approve --channel wechat`.
- **allowlist**: Only wxids in `allowFrom` can message the bot.
- **open**: Anyone can message. Flagged as a security warning.
- **disabled**: All DMs blocked.

```json5
{
  channels: {
    wechat: {
      dmPolicy: "allowlist",
      allowFrom: ["wxid_yourown123", "wxid_friend456"]
    }
  }
}
```

### Groups

Controlled by `groupPolicy` (default: `"allowlist"`):

- **allowlist**: Only responds in groups where the bot is a member and sender is in allowFrom.
- **open**: Responds in any group.
- **disabled**: Ignores all group messages.

The `requireMention` flag (default: `true`) ensures the bot only responds when @mentioned in groups.

## How it works

### Message flow

1. WeChat message arrives via puppet protocol
2. Wechaty emits `message` event
3. Monitor dispatches by message type (text, audio, image, video, contact, url)
4. DM policy / pairing check
5. Group @mention check (if applicable)
6. Route to agent, format envelope, record session
7. LLM processes and generates reply
8. Reply delivered via `contact.say()` or `room.say()`

### Session isolation

Each DM contact and each group room gets its own session. Sessions are keyed by `wechat:<wxid>` for DMs and `wechat:group:<roomId>` for groups.

## WeChat-specific features

### Voice messages

Voice messages are automatically transcribed (default: enabled). Configure the provider:

```json5
{
  channels: {
    wechat: {
      voice: {
        transcribe: true,
        provider: "openai",       // "openai" or "system"
        openaiApiKey: "sk-..."    // required for openai provider
      }
    }
  }
}
```

- **openai**: Converts SILK audio to MP3 via ffmpeg, then transcribes with Whisper API. Requires ffmpeg installed.
- **system**: macOS Speech.framework (experimental, macOS only).

Transcribed messages appear as `[Voice: <transcript>]` in the agent context.

### Moments feed

Read-only Moments polling (padlocal only). New Moments from contacts are injected as agent context:

```json5
{
  channels: {
    wechat: {
      moments: {
        enabled: true,
        pollIntervalSeconds: 300,
        injectAsContext: true,
        maxPerPoll: 20
      }
    }
  }
}
```

### Contact index

Builds a searchable index of contacts and shared groups on login:

```json5
{
  channels: {
    wechat: {
      contacts: {
        indexEnabled: true,
        refreshIntervalHours: 24
      }
    }
  }
}
```

The index is persisted to `~/.openclaw/credentials/wechat/<accountId>/contacts.json`.

### Ack reaction

Send an emoji reaction to acknowledge receipt before processing:

```json5
{
  channels: {
    wechat: {
      ackReaction: {
        emoji: "eyes",
        direct: false,
        group: "mentions"
      }
    }
  }
}
```

## Limits

- **Text chunk limit**: 2000 characters per message
- **Inbound media**: configurable via `mediaMaxMb` (default: 50 MB)
- **Min reply delay**: configurable via `minReplyDelayMs` (default: 500ms) — reduces spam detection risk

## Agent tool

The `send` action sends messages to contacts or groups:

```
wechat.send({ to: "wxid_xxxxx", message: "Hello!" })
wechat.send({ to: "12345@chatroom", message: "Group message" })
```

## Delivery targets (CLI/cron)

```bash
openclaw send --channel wechat --to wxid_xxxxx "Hello from CLI"
```

Target format: `wechat:<wxid>` for DMs, `wechat:<roomId>` for groups.

## Troubleshooting

### QR code not showing

Ensure `qrcode-terminal` is installed. The fallback prints a URL you can open in a browser.

### Login blocked

Some WeChat accounts cannot use web protocol (wechat4u). Switch to padlocal puppet.

### Voice transcription fails

- Ensure ffmpeg is installed: `brew install ffmpeg`
- For OpenAI provider: verify `openaiApiKey` is set and valid

### Bot disconnects frequently

PadLocal connections may drop if the token is shared across instances. Use one token per account.

### Check status

```bash
openclaw channels status --channel wechat
```

## Configuration reference

- `channels.wechat.puppet` — `"padlocal"` | `"wechat4u"` (default: `"padlocal"`)
- `channels.wechat.padlocalToken` — PadLocal puppet token
- `channels.wechat.dmPolicy` — `"pairing"` | `"allowlist"` | `"open"` | `"disabled"` (default: `"pairing"`)
- `channels.wechat.allowFrom` — Array of wxid strings for allowlist
- `channels.wechat.groupPolicy` — `"allowlist"` | `"open"` | `"disabled"` (default: `"allowlist"`)
- `channels.wechat.requireMention` — Require @mention in groups (default: `true`)
- `channels.wechat.voice.transcribe` — Enable voice transcription (default: `true`)
- `channels.wechat.voice.provider` — `"system"` | `"openai"` (default: `"system"`)
- `channels.wechat.voice.openaiApiKey` — OpenAI API key for Whisper
- `channels.wechat.moments.enabled` — Enable Moments polling (default: `false`)
- `channels.wechat.moments.pollIntervalSeconds` — Poll interval (default: `300`)
- `channels.wechat.moments.injectAsContext` — Inject as agent context (default: `true`)
- `channels.wechat.moments.maxPerPoll` — Max moments per poll (default: `20`)
- `channels.wechat.contacts.indexEnabled` — Build contact index (default: `true`)
- `channels.wechat.contacts.refreshIntervalHours` — Refresh interval (default: `24`)
- `channels.wechat.minReplyDelayMs` — Min delay before reply (default: `500`)
- `channels.wechat.mediaMaxMb` — Max inbound media size in MB (default: `50`)
- `channels.wechat.ackReaction.emoji` — Ack reaction emoji (default: empty/disabled)
- `channels.wechat.ackReaction.direct` — React in DMs (default: `false`)
- `channels.wechat.ackReaction.group` — React in groups: `"always"` | `"mentions"` | `"never"` (default: `"mentions"`)
- `channels.wechat.accounts.<id>.*` — Per-account overrides for any of the above
- `channels.wechat.defaultAccount` — Default account ID for multi-account

## Related global options

- `session.store` — Session storage path
- `commands.useAccessGroups` — Access group enforcement
- `markdown.tables` — Markdown table rendering mode (`off` | `bullets` | `code`)
