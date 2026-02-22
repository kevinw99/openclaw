# Tasks: WeChat Channel Extension

## Overview

Task breakdown for building the WeChat channel extension (`extensions/wechat/`). Implementation follows the Zalo extension as the reference pattern. Tasks are ordered by dependency; Phases 1–3 are the critical path for core messaging. Phases 4–5 add WeChat-specific capabilities.

---

## Phase 1: Scaffolding and Configuration

### Task 1.1: Create Extension Directory and Package Manifest

- **Status**: Not Started
- **Description**: Set up the `extensions/wechat/` directory with all required scaffolding files matching the Zalo extension structure.
- **Acceptance Criteria**:
  - [ ] `extensions/wechat/` directory created
  - [ ] `package.json` created with deps: `wechaty`, `wechaty-puppet-padlocal`, `wechaty-puppet-wechat4u`
  - [ ] `openclaw.plugin.json` created: `{ id: "wechat", channels: ["wechat"] }`
  - [ ] `index.ts` created with plugin entry point skeleton
  - [ ] `tsconfig.json` configured (extends workspace root)
  - [ ] Extension registered in workspace `pnpm-workspace.yaml`

### Task 1.2: Define Config Schema (`config-schema.ts`)

- **Status**: Not Started
- **Description**: Write the Zod schema for all `channels.wechat.*` configuration fields with validation and defaults.
- **Acceptance Criteria**:
  - [ ] `puppet` field: `"padlocal" | "wechat4u"`, default `"padlocal"`
  - [ ] `padlocalToken` field: string, required when puppet=padlocal (custom validator)
  - [ ] `dmPolicy`, `allowFrom`, `groupPolicy`, `requireMention` fields
  - [ ] `voice` sub-schema: `transcribe`, `provider`, `openaiApiKey`
  - [ ] `moments` sub-schema: `enabled`, `pollIntervalSeconds`, `injectAsContext`, `maxPerPoll`
  - [ ] `contacts` sub-schema: `indexEnabled`, `refreshIntervalHours`
  - [ ] `minReplyDelayMs`, `mediaMaxMb`, `ackReaction` fields
  - [ ] `accounts.<id>` override structure
  - [ ] Zod validation error messages are human-readable

### Task 1.3: Implement Account Resolution (`accounts.ts`)

- **Status**: Not Started
- **Description**: Functions to resolve a configured WeChat account from `openclaw.json`, with multi-account support.
- **Acceptance Criteria**:
  - [ ] `resolveWeChatAccount(cfg, accountId)` resolves merged config (base + account override)
  - [ ] `listWeChatAccountIds(cfg)` returns list of configured account IDs
  - [ ] `resolveDefaultWeChatAccountId(cfg)` returns `"default"` or first account
  - [ ] Account token source identified: `config` or `env` (`WECHAT_PADLOCAL_TOKEN`)
  - [ ] Missing padlocal token on padlocal puppet → clear error

### Task 1.4: Implement Runtime Singleton (`runtime.ts`)

- **Status**: Not Started
- **Description**: Standard PluginRuntime singleton (identical pattern to Zalo).
- **Acceptance Criteria**:
  - [ ] `setWeChatRuntime(runtime)` stores runtime
  - [ ] `getWeChatRuntime()` returns runtime or throws if uninitialized

---

## Phase 2: Core Bot Lifecycle

### Task 2.1: Implement Bot Factory (`bot.ts`)

- **Status**: Not Started
- **Blocked by**: Task 1.3
- **Description**: Create and manage Wechaty bot instances — one per account.
- **Acceptance Criteria**:
  - [ ] `createWechatyBot(account)` builds Wechaty instance with correct puppet
  - [ ] padlocal puppet instantiated with `token` from account config
  - [ ] wechat4u puppet instantiated for dev/test accounts
  - [ ] Session name set to `openclaw-wechat-<accountId>` for persistence
  - [ ] Session file symlinked to `~/.openclaw/credentials/wechat/<accountId>/session.json`
  - [ ] Bot instances cached per accountId (singleton per account)

### Task 2.2: Implement QR Login Onboarding (`onboarding.ts`)

- **Status**: Not Started
- **Blocked by**: Task 2.1
- **Description**: Adapt Wechaty's QR scan flow to OpenClaw's `openclaw channels login` command.
- **Acceptance Criteria**:
  - [ ] `scan` event: QR code printed as ASCII art to terminal via `qrcode-terminal`
  - [ ] `scan` event: QR PNG served at `GET /wechat/qr/<accountId>` (for GUI clients)
  - [ ] `login` event: logs user display name and wxid; marks account as linked
  - [ ] `logout` event: marks account as unlinked; prompts re-login
  - [ ] `openclaw channels logout --channel wechat` deletes session file and calls `bot.logout()`

### Task 2.3: Implement Health Probe (`probe.ts`)

- **Status**: Not Started
- **Blocked by**: Task 2.1
- **Description**: Health check that reports bot connection state.
- **Acceptance Criteria**:
  - [ ] `probeWeChatAccount(bot)` returns `{ ok, user, puppet }`
  - [ ] `bot.logonoff()` used for logged-in check
  - [ ] `bot.currentUser` used to get display name
  - [ ] Timeout supported (default 3000ms)

### Task 2.4: Implement Status Issues (`status-issues.ts`)

- **Status**: Not Started
- **Blocked by**: Task 2.3
- **Description**: Detect and report common connectivity issues for `openclaw channels status`.
- **Acceptance Criteria**:
  - [ ] Issue: not logged in / QR required
  - [ ] Issue: puppet error / connection lost
  - [ ] Issue: padlocal token invalid or expired
  - [ ] Issue: session file missing or corrupted

---

## Phase 3: Message Processing Pipeline

### Task 3.1: Implement Message Monitor (`monitor.ts`)

- **Status**: Not Started
- **Blocked by**: Task 2.1, Task 1.4
- **Description**: Register Wechaty event handlers and implement the full inbound message processing pipeline.
- **Acceptance Criteria**:
  - [ ] `bot.on('scan')` → QR display
  - [ ] `bot.on('login')` → status update
  - [ ] `bot.on('logout')` → status update
  - [ ] `bot.on('error')` → log + status update
  - [ ] `bot.on('message')` → `processMessage()`:
    - [ ] Skip `msg.self()` (own messages)
    - [ ] Skip `msg.age() > 60s` (stale messages)
    - [ ] Dispatch by `msg.type()`:
      - [ ] `Text` → `processTextMessage()`
      - [ ] `Audio` → `voice.transcribe()` → `processTextMessage()`
      - [ ] `Image` / `Video` → save media → `processMediaMessage()`
      - [ ] `Contact` → render as `<contact: Name (wxid)>` → `processTextMessage()`
      - [ ] `Url` → render as `<link: title — url>` → `processTextMessage()`
      - [ ] `Recalled` / `Emoticon` / `Unknown` → skip with log
  - [ ] `processTextMessage()`:
    - [ ] Extract `room`, `from`, `chatId`, `senderId`, `senderName`
    - [ ] Group: check `requireMention` → `msg.mentionSelf()`; skip if not mentioned
    - [ ] DM policy enforcement (pairing / allowlist / open / disabled)
    - [ ] Pairing flow: send pairing code via `contact.say()`
    - [ ] Ack reaction if configured
    - [ ] Route via `core.channel.routing.resolveAgentRoute()`
    - [ ] Format envelope via `core.channel.reply.formatAgentEnvelope()`
    - [ ] Record session via `core.channel.session.recordInboundSession()`
    - [ ] Dispatch reply via `core.channel.reply.dispatchReplyWithBufferedBlockDispatcher()`
  - [ ] `minReplyDelayMs` enforced before delivery

### Task 3.2: Implement Outbound Send (`send.ts`)

- **Status**: Not Started
- **Blocked by**: Task 2.1
- **Description**: Deliver agent replies to WeChat contacts or groups via the Wechaty bot.
- **Acceptance Criteria**:
  - [ ] `sendWeChatText(to, text, bot)` → `contact.say(text)` or `room.say(text)`
  - [ ] DM vs group detected from `to` format (chatroom suffix)
  - [ ] Contact / room lookup failure → error returned (not thrown)
  - [ ] Long text chunked at 2000 chars with newline-aware splitting
  - [ ] `sendWeChatMedia(to, filePath, bot)` → `contact.say(FileBox.fromFile(path))`
  - [ ] Caption sent as separate message after media

### Task 3.3: Implement Tool Actions (`actions.ts`)

- **Status**: Not Started
- **Blocked by**: Task 3.2
- **Description**: WeChat-specific tool actions available to the agent.
- **Acceptance Criteria**:
  - [ ] `react` action: send emoji reaction to a message (padlocal only)
  - [ ] `forward` action: forward a message to another contact or room
  - [ ] Actions gated by config (`channels.wechat.actions.*`)
  - [ ] Action schema follows existing channel action pattern

### Task 3.4: Implement Channel Plugin and Dock (`channel.ts`)

- **Status**: Not Started
- **Blocked by**: Tasks 1.2, 1.3, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3
- **Description**: Assemble the full `ChannelPlugin` and `ChannelDock` objects and wire the `gateway.startAccount` lifecycle.
- **Acceptance Criteria**:
  - [ ] `ChannelDock` declared:
    - [ ] `chatTypes: ["direct", "group"]`
    - [ ] `capabilities: { media: true, reactions: true, threads: false }`
    - [ ] `outbound.textChunkLimit: 2000`
    - [ ] `groups.resolveRequireMention` reads from config
  - [ ] `ChannelPlugin` declared with all required fields
  - [ ] `gateway.startAccount` creates bot, registers event handlers, calls `bot.start()`
  - [ ] `gateway.startAccount` returns `stop()` that calls `bot.stop()`
  - [ ] `directory.listPeers` returns contacts from index
  - [ ] `directory.listGroups` returns room list
  - [ ] `setup` section handles `openclaw channels setup wechat`

### Task 3.5: Wire Plugin Entry (`index.ts`)

- **Status**: Not Started
- **Blocked by**: Task 3.4
- **Description**: Complete the plugin entry point.
- **Acceptance Criteria**:
  - [ ] `plugin.register(api)` calls `setWeChatRuntime`, registers channel, registers HTTP handler
  - [ ] QR HTTP handler (`GET /wechat/qr/<accountId>`) registered
  - [ ] Plugin exported as default

---

## Phase 4: WeChat-Specific Features

### Task 4.1: Voice Message Transcription (`voice.ts`)

- **Status**: Not Started
- **Blocked by**: Task 3.1
- **Description**: Transcribe WeChat SILK audio messages to text before routing to agent.
- **Acceptance Criteria**:
  - [ ] `transcribeVoiceMessage(msg, config)` downloads audio via `msg.toFileBox()`
  - [ ] SILK → MP3 conversion via ffmpeg (required for OpenAI path)
  - [ ] `provider: "openai"`: calls `openai.audio.transcriptions.create({ model: "whisper-1" })`
  - [ ] `provider: "system"`: calls macOS Speech via shell subprocess (reuses Swabble helper)
  - [ ] Returns `"[Voice: <transcript>]"` on success
  - [ ] Returns `"[Voice message — transcription unavailable]"` on failure
  - [ ] Temp files cleaned up after use
  - [ ] Feature disabled (`transcribe: false`) → returns `"[Voice message]"` placeholder

### Task 4.2: Moments Feed Polling (`moments.ts`)

- **Status**: Not Started
- **Blocked by**: Task 2.1, Task 3.4
- **Description**: Background polling of WeChat Moments (padlocal only) with context injection.
- **Acceptance Criteria**:
  - [ ] `startMomentsPoller(bot, config, core)` starts interval on login
  - [ ] Skips start if puppet is not padlocal; logs warning
  - [ ] Calls `(bot.puppet as PadLocalPuppet).getMoments({ count: maxPerPoll })`
  - [ ] Deduplicates: only processes moments newer than last poll timestamp
  - [ ] Formats each moment as structured text block (author, text, images, likes, top comments)
  - [ ] Injects into agent session context via `core.channel.session.injectContext()`
  - [ ] Poller stopped cleanly on `bot.on('logout')` or `stop()`
  - [ ] `stopMomentsPoller()` exported for cleanup

### Task 4.3: Contact Graph Indexing (`contact-graph.ts`)

- **Status**: Not Started
- **Blocked by**: Task 2.1
- **Description**: Build and maintain an indexed, searchable contact list for relationship context.
- **Acceptance Criteria**:
  - [ ] `buildContactIndex(bot, accountId)` loads all contacts + rooms on login
  - [ ] Index includes: wxid, display name, remark, tags, shared room names
  - [ ] Index persisted to `~/.openclaw/credentials/wechat/<accountId>/contacts.json`
  - [ ] `refreshContactIndex(bot, accountId)` refreshes on configurable interval
  - [ ] `searchContacts(query, accountId)` searches name / remark / tag
  - [ ] Agent tool `wechat_contacts` registered: `{ query: string } → ContactNode[]`
  - [ ] Index available at message processing time for sender enrichment

---

## Phase 5: Documentation and Tests

### Task 5.1: Write Channel Documentation (`docs/channels/wechat.md`)

- **Status**: Not Started
- **Blocked by**: Phase 3 complete
- **Description**: Write end-user documentation following the format of `docs/channels/whatsapp.md`.
- **Acceptance Criteria**:
  - [ ] Quick setup section (install puppet, get token, scan QR)
  - [ ] Config reference (all `channels.wechat.*` fields)
  - [ ] Login and credential management
  - [ ] Inbound / outbound flow description
  - [ ] Groups: @mention, group policy
  - [ ] Voice message transcription setup
  - [ ] Moments setup (padlocal only, clearly marked)
  - [ ] Troubleshooting section
  - [ ] Account safety notes (rate limiting, ban risk)

### Task 5.2: Write Unit Tests

- **Status**: Not Started
- **Blocked by**: Task 3.1, Task 4.1
- **Description**: Unit tests for core message pipeline using mock puppet.
- **Acceptance Criteria**:
  - [ ] `processMessage` test: text DM → correct envelope built
  - [ ] `processMessage` test: group + no mention → skipped
  - [ ] `processMessage` test: group + mention → dispatched
  - [ ] `processMessage` test: Audio type → voice.transcribe called
  - [ ] DM policy tests: pairing / allowlist / open / disabled
  - [ ] Voice transcription: mock openai call succeeds
  - [ ] Voice transcription: failure → placeholder returned
  - [ ] Contact graph: search returns correct matches
  - [ ] Config schema: padlocal without token → validation error

### Task 5.3: Integration Test with Mock Puppet

- **Status**: Not Started
- **Blocked by**: Task 5.2
- **Description**: End-to-end test using `wechaty-puppet-mock`.
- **Acceptance Criteria**:
  - [ ] Mock bot starts without real credentials
  - [ ] Simulated inbound text DM → agent reply sent
  - [ ] Simulated inbound group @mention → agent reply sent
  - [ ] Simulated inbound group without @mention → no reply
  - [ ] `openclaw channels status` shows correct state

---

## Task Summary

| Phase     | Description              | Tasks  | Est. Complexity |
| --------- | ------------------------ | ------ | --------------- |
| Phase 1   | Scaffolding & Config     | 4      | Low             |
| Phase 2   | Bot Lifecycle            | 4      | Medium          |
| Phase 3   | Message Pipeline         | 5      | High            |
| Phase 4   | WeChat-Specific Features | 3      | Medium–High     |
| Phase 5   | Docs & Tests             | 3      | Medium          |
| **Total** |                          | **19** |                 |

---

## Dependencies

```
1.1 → 1.2, 1.3, 1.4          (scaffolding first)
1.3 → 2.1                    (account resolution before bot factory)
2.1 → 2.2, 2.3, 3.2, 4.2, 4.3
2.3 → 2.4
1.2, 1.3, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3 → 3.4  (channel.ts is assembler)
3.4 → 3.5                    (index.ts last)
3.1 → 4.1                    (voice called inside processMessage)
3.4 → 4.2                    (moments poller starts in startAccount)
Phase 3 complete → 5.1       (docs after core works)
3.1, 4.1 → 5.2
5.2 → 5.3
```

## Recommended Priority Order

1. **Critical path** (minimum viable channel):
   - 1.1 → 1.2 → 1.3 → 1.4 → 2.1 → 2.2 → 3.1 → 3.2 → 3.4 → 3.5

2. **High priority** (production readiness):
   - 2.3 → 2.4 (health / status)
   - 3.3 (tool actions)
   - 4.1 (voice — critical for Chinese WeChat usage)
   - 5.1 (docs)

3. **WeChat-specific value** (spec 01 context integration):
   - 4.2 (Moments — padlocal token required)
   - 4.3 (contact graph)

4. **Quality**:
   - 5.2, 5.3 (tests)

---

**Last Updated**: 2026-02-19
