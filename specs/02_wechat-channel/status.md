# Status: WeChat Channel Extension

**Overall Status**: BLOCKED — PadLocal is dead; implementation complete but cannot proceed to integration testing
**Started**: 2026-02-19
**Last Updated**: 2026-02-19

---

## Progress

| Phase                             | Status   | Notes                                                                  |
| --------------------------------- | -------- | ---------------------------------------------------------------------- |
| Phase 1: Scaffolding & Config     | Complete | package.json, plugin manifest, types, config schema, accounts, runtime |
| Phase 2: Bot Lifecycle            | Complete | bot.ts, onboarding.ts, probe.ts, status-issues.ts                      |
| Phase 3: Message Pipeline         | Complete | monitor.ts, send.ts, actions.ts, channel.ts, index.ts                  |
| Phase 4: WeChat-Specific Features | Complete | voice.ts, moments.ts, contact-graph.ts                                 |
| Phase 5: Docs & Tests             | Complete | docs written; 9 test files (5 prior + 4 new)                           |

## Files Created

- `extensions/wechat/package.json`
- `extensions/wechat/openclaw.plugin.json`
- `extensions/wechat/index.ts`
- `extensions/wechat/src/types.ts`
- `extensions/wechat/src/config-schema.ts`
- `extensions/wechat/src/accounts.ts`
- `extensions/wechat/src/runtime.ts`
- `extensions/wechat/src/bot.ts`
- `extensions/wechat/src/onboarding.ts`
- `extensions/wechat/src/probe.ts`
- `extensions/wechat/src/status-issues.ts`
- `extensions/wechat/src/monitor.ts`
- `extensions/wechat/src/send.ts`
- `extensions/wechat/src/actions.ts`
- `extensions/wechat/src/channel.ts`
- `extensions/wechat/src/voice.ts`
- `extensions/wechat/src/moments.ts`
- `extensions/wechat/src/contact-graph.ts`
- `docs/channels/wechat.md`

### Test Files

- `extensions/wechat/src/config-schema.test.ts` (prior)
- `extensions/wechat/src/accounts.test.ts` (prior)
- `extensions/wechat/src/send.test.ts` (prior)
- `extensions/wechat/src/status-issues.test.ts` (prior)
- `extensions/wechat/src/channel.directory.test.ts` (prior)
- `extensions/wechat/src/bot.test.ts` — handleWeChatMessage pipeline (new)
- `extensions/wechat/src/probe.test.ts` — health probe (new)
- `extensions/wechat/src/contact-graph.test.ts` — contact search (new)
- `extensions/wechat/src/moments.test.ts` — Moments poller (new)

### Bug Fixes

- Fixed `sendWeChatMessage` call signature in monitor.ts, channel.ts, actions.ts (was using positional args instead of single object param)

## Decisions Log

| Date       | Decision                              | Rationale                                                    |
| ---------- | ------------------------------------- | ------------------------------------------------------------ |
| 2026-02-19 | Use Wechaty as puppet layer           | TypeScript-native, consistent with OpenClaw runtime          |
| 2026-02-19 | padlocal as primary puppet            | Most stable, supports Moments, works with modern accounts    |
| 2026-02-19 | wechat4u for dev/test only            | Free but web protocol (blocked for post-2017 accounts)       |
| 2026-02-19 | Moments = read-only, polling          | No push API available; padlocal-only feature                 |
| 2026-02-19 | Voice transcription via config        | Support both local (macOS Speech) and cloud (OpenAI Whisper) |
| 2026-02-19 | Follow Zalo extension pattern exactly | Same file structure, SDK patterns, account resolution        |

## Blockers

- **CRITICAL: PadLocal is dead (confirmed 2026-02).**
  - npm package last published 3+ years ago (2022)
  - pad-local.com is down (502)
  - GitHub issues unanswered; maintainer unresponsive
  - WeChat protocol updates broke login: "你的应用版本过低"
  - **This blocks ALL integration testing for Spec 02.**
  - See: [Spec 04](../04_wechat-continuous-sync/) for replacement approach
- System voice transcription (macOS Speech.framework) is stubbed — needs Swift helper
- ~~Dependencies not installed~~ — resolved (pnpm install successful, all 89 tests pass)
- ~~padlocal token needed~~ — PadLocal is dead, token cannot be obtained
- monitor.ts duplicates the pipeline from bot.ts — should be refactored to call handleWeChatMessage

## Notes

- ~~padlocal trial token (7 days free) available at https://github.com/wechaty/puppet-padlocal~~ — site is down
- Reference implementation: `extensions/zalo/` in this repo
- All 19 source files created following Zalo extension patterns
- **Next steps**: See [Spec 04](../04_wechat-continuous-sync/) for the replacement strategy to get WeChat messages continuously
