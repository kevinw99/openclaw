# Requirements: WeChat Channel Extension

## Objective

Build a native OpenClaw channel extension for WeChat personal accounts that enables the Full Context AI Personal Assistant (spec 01) to read, understand, and respond to WeChat communications — including DMs, group chats, voice messages, and Moments.

---

## Scope

### In Scope

- WeChat personal account integration via Wechaty puppet layer
- Inbound and outbound direct messages
- Inbound and outbound group chat messages
- Voice message transcription (text conversion)
- Image, video, and file receive/send
- Moments (朋友圈) feed reading and context injection
- Contact graph indexing (names, remarks, tags, shared groups)
- QR code login and session persistence
- Multi-account support (e.g., personal + work WeChat)
- OpenClaw DM policy enforcement (pairing / allowlist / open / disabled)
- Group @mention gating
- Emoji reactions

### Out of Scope

- WeChat Official Accounts (公众号) subscription articles
- WeChat Channels (视频号) short video platform
- WeChat Work / WeCom (enterprise, separate product)
- Mini Programs (小程序)
- Posting to Moments (read-only in initial cut)
- Red packets / payment features
- Real-time Moments notifications (polling only, not push)

### Dependencies

- Wechaty ^1.x (Node.js/TypeScript)
- `wechaty-puppet-padlocal` — primary puppet (paid token required)
- `wechaty-puppet-wechat4u` — dev/test fallback (free, web protocol)
- OpenClaw plugin SDK (`openclaw/plugin-sdk`)
- OpenClaw gateway >= current version
- padlocal token for production use (~$15/mo or trial token for dev)
- Optional: OpenAI API key (for Whisper voice transcription)

---

## Functional Requirements

### FR1: Direct Message Receive

- **Description**: Receive WeChat DMs from contacts and route to the OpenClaw agent pipeline
- **Acceptance Criteria**:
  - [ ] Text DMs received and dispatched to agent
  - [ ] DM policy enforced (pairing / allowlist / open / disabled)
  - [ ] Unknown senders trigger pairing flow (code sent back via WeChat DM)
  - [ ] Self-messages (sent from same account) are skipped
  - [ ] Message envelope includes sender wxid, display name, and timestamp

### FR2: Direct Message Send

- **Description**: Agent replies are delivered as WeChat DMs
- **Acceptance Criteria**:
  - [ ] Text replies sent to originating contact
  - [ ] Long messages chunked at 2000 chars (WeChat soft limit)
  - [ ] Image/file attachments supported
  - [ ] Delivery errors logged; non-fatal to agent response

### FR3: Group Chat Receive

- **Description**: Receive WeChat group messages and route to agent
- **Acceptance Criteria**:
  - [ ] Group messages received with room ID, room topic, sender name
  - [ ] `requireMention: true` (default): only trigger when bot is @mentioned
  - [ ] `requireMention: false`: always trigger (configurable per group)
  - [ ] Group policy enforced (allowlist / open / disabled)
  - [ ] History context injected for recent unprocessed messages (configurable limit)
  - [ ] Sender suffix appended: `[from: Name (wxid)]`

### FR4: Group Chat Send

- **Description**: Agent replies are delivered to the group chat
- **Acceptance Criteria**:
  - [ ] Text replies sent to originating room
  - [ ] @mention sender in reply (configurable)
  - [ ] Long messages chunked appropriately

### FR5: Voice Message Transcription

- **Description**: Incoming voice messages (WeChat voice bubbles) are transcribed to text before reaching the agent
- **Acceptance Criteria**:
  - [ ] Voice messages detected (MessageType.Audio)
  - [ ] Audio file downloaded via `toFileBox()`
  - [ ] Transcription dispatched to configured provider:
    - `system` — macOS Speech framework (local, free)
    - `openai` — OpenAI Whisper API (cloud, requires key)
  - [ ] Transcribed text forwarded as `[Voice: <transcript>]` to agent
  - [ ] Original audio saved optionally (configurable)
  - [ ] Transcription failure falls back to `[Voice message — transcription unavailable]`

### FR6: Media Receive

- **Description**: Images, videos, and files received and made available to agent
- **Acceptance Criteria**:
  - [ ] Image messages: download, save locally, pass as `MediaPath` to agent
  - [ ] Video messages: save locally, pass as `MediaPath` with `MediaType: video/*`
  - [ ] File/document attachments: save locally, pass filename and path
  - [ ] Stickers: log as `<sticker>` placeholder, do not pass to agent
  - [ ] Contact cards: render as `<contact: DisplayName (wxid)>`
  - [ ] URL link previews: render as `<link: title — url>`
  - [ ] Media size cap configurable (`mediaMaxMb`, default 50 MB inbound, 5 MB outbound)

### FR7: Media Send

- **Description**: Agent can send images and files as WeChat messages
- **Acceptance Criteria**:
  - [ ] Image send: local path or URL → WeChat image message
  - [ ] File send: local path → WeChat file message
  - [ ] Caption on first media item only (WeChat limitation)

### FR8: Emoji Reactions

- **Description**: Bot can react to received messages with emoji
- **Acceptance Criteria**:
  - [ ] Acknowledgment reaction on message receipt (configurable emoji, default: off)
  - [ ] Agent can trigger reaction via tool action
  - [ ] Works in both DMs and groups (padlocal only)

### FR9: QR Login and Session Persistence

- **Description**: User authenticates by scanning a QR code; session survives gateway restarts
- **Acceptance Criteria**:
  - [ ] `openclaw channels login --channel wechat` triggers QR display
  - [ ] QR rendered in terminal (ASCII art) and optionally served as PNG at `/wechat/qr`
  - [ ] Login event logged; user info stored in session
  - [ ] Session file persisted to `~/.openclaw/credentials/wechat/<accountId>/session.json`
  - [ ] Session auto-restored on gateway restart without re-scan
  - [ ] Logout event detected; status updated, user notified
  - [ ] `openclaw channels logout --channel wechat` clears session

### FR10: Multi-Account Support

- **Description**: Run multiple WeChat accounts in a single gateway process
- **Acceptance Criteria**:
  - [ ] Each account configured independently under `channels.wechat.accounts.<accountId>`
  - [ ] Each account has its own Wechaty bot instance
  - [ ] Default account (`default`) used when no `--account` flag
  - [ ] Account-level overrides for puppet, token, DM policy, voice, and media settings

### FR11: Moments Feed Reading

- **Description**: Poll the WeChat Moments feed and inject recent posts as agent context (padlocal puppet only)
- **Acceptance Criteria**:
  - [ ] Moments polling enabled via config (`moments.enabled: true`)
  - [ ] Poll interval configurable (`moments.pollIntervalSeconds`, default: 300)
  - [ ] Each Moment parsed: author, text content, image count, like count, top comments
  - [ ] New Moments (since last poll) injected into agent session context as structured text:
    ```
    [WeChat Moment — <Name>, <timestamp>]
    <text content>
    [<N> images] [<L> likes] [<C> comments: <top 2 comments>]
    ```
  - [ ] Only available with padlocal puppet; config validation error on other puppets
  - [ ] Moments not treated as messages (no reply dispatched)

### FR12: Contact Graph Indexing

- **Description**: Build and maintain an index of the user's WeChat contacts for relationship context
- **Acceptance Criteria**:
  - [ ] On login, load full contact list
  - [ ] For each contact: wxid, display name, remark (备注), tags, shared group names
  - [ ] Index persisted to `~/.openclaw/credentials/wechat/<accountId>/contacts.json`
  - [ ] Agent tool `wechat_contacts` available: search contacts by name/remark/tag
  - [ ] Index refreshed periodically (configurable, default: every 24 hours)
  - [ ] Relationship strength inferred from recent interaction frequency (last 30 days)

### FR13: Status and Health

- **Description**: Channel reports connection health to `openclaw channels status`
- **Acceptance Criteria**:
  - [ ] Reports: puppet type, login status, account name, last inbound/outbound timestamps
  - [ ] Reports Moments poller status (if enabled)
  - [ ] `openclaw doctor` includes WeChat connectivity checks
  - [ ] Probe method: `bot.logonoff()` + `bot.currentUser`
  - [ ] Reconnect on session drop (exponential backoff, max attempts configurable)

---

## Non-Functional Requirements

### NFR1: Account Safety

- Bot behavior must minimize detection risk by Tencent's anti-bot systems
- Use padlocal puppet (lower detection surface than web protocol)
- Configurable rate limiting on outbound messages (`minReplyDelayMs`, default: 500ms)
- No mass-messaging or broadcast behavior

### NFR2: Reliability

- Gateway restart must not require re-scan (session file persistence)
- Wechaty errors caught and logged; gateway continues running
- Message processing errors are non-fatal: log and continue

### NFR3: Performance

- Message processing latency (receive → agent dispatch): < 1 second
- Voice transcription: < 10 seconds (acceptable user-facing delay)
- Moments poll: non-blocking background task

### NFR4: Privacy

- No WeChat message content sent to external services except:
  - The OpenClaw LLM provider (configured by user)
  - OpenAI Whisper, only if `voice.provider = "openai"` is explicitly set
- Session credentials stored locally only
- Contact index stored locally only

### NFR5: Configurability

- All behavior tunable via `openclaw.json` `channels.wechat.*` config section
- Sane defaults for all options (no config required beyond puppet token)

### NFR6: Compatibility

- Node.js 22+ (OpenClaw requirement)
- TypeScript strict mode
- Must not break existing channels if WeChat extension is not installed

---

## Risk Register

| Risk                                      | Severity | Likelihood | Mitigation                                                                       |
| ----------------------------------------- | -------- | ---------- | -------------------------------------------------------------------------------- |
| Tencent bans bot account                  | High     | Medium     | Use padlocal; rate-limit outbound; avoid patterns typical of spam bots           |
| padlocal service goes down                | Medium   | Low        | Design puppet as pluggable config; fallback path documented                      |
| WeChat protocol change breaks puppet      | Medium   | Medium     | Pin puppet version; monitor wechaty/puppet-padlocal GitHub                       |
| Moments API not exposed by free puppets   | High     | Confirmed  | Moments = padlocal-only; clearly documented; config validation error on mismatch |
| Web WeChat blocked for post-2017 accounts | High     | Confirmed  | Default to padlocal; wechat4u for dev/test only with clear warning               |
| padlocal pricing changes                  | Low      | Low        | Abstract puppet layer; switching cost is config change only                      |

---

## Quality Requirements

- **Unit test coverage**: core message processing pipeline (mock puppet)
- **Integration test**: loopback message test with mock puppet
- **Documentation**: channel doc at `docs/channels/wechat.md` matching format of `docs/channels/whatsapp.md`
- **Config validation**: Zod schema for all `channels.wechat.*` fields with helpful error messages

---

**Last Updated**: 2026-02-19
