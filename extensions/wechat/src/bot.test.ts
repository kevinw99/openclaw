import { describe, expect, it, vi, beforeEach } from "vitest";
import type { ResolvedWeChatAccount } from "./types.js";

// ---------------------------------------------------------------------------
// Module mocks — must be before imports that use them
// ---------------------------------------------------------------------------

const mockShouldLogVerbose = vi.fn(() => false);
const mockSaveMediaBuffer = vi.fn().mockResolvedValue({
  path: "/tmp/test-media.jpg",
  contentType: "image/jpeg",
});
const mockShouldComputeCommandAuthorized = vi.fn(() => false);
const mockResolveCommandAuthorizedFromAuthorizers = vi.fn(() => false);
const mockIsControlCommandMessage = vi.fn(() => false);
const mockReadAllowFromStore = vi.fn().mockResolvedValue([]);
const mockUpsertPairingRequest = vi.fn().mockResolvedValue({ code: "TEST123", created: true });
const mockBuildPairingReply = vi.fn(() => "Pairing code: TEST123");
const mockResolveAgentRoute = vi.fn(() => ({
  agentId: "main",
  accountId: "default",
  sessionKey: "agent:main:wechat:dm:wxid_sender123",
}));
const mockResolveStorePath = vi.fn(() => "/tmp/sessions");
const mockReadSessionUpdatedAt = vi.fn(() => undefined);
const mockRecordInboundSession = vi.fn().mockResolvedValue(undefined);
const mockResolveEnvelopeFormatOptions = vi.fn(() => ({}));
const mockFormatAgentEnvelope = vi.fn(({ body }: { body: string }) => body);
const mockFinalizeInboundContext = vi.fn((ctx: Record<string, unknown>) => ctx);
const mockDispatch = vi.fn().mockResolvedValue(undefined);
const mockResolveMarkdownTableMode = vi.fn(() => "code");
const mockConvertMarkdownTables = vi.fn((text: string) => text);
const mockResolveChunkMode = vi.fn(() => "default");
const mockChunkMarkdownTextWithMode = vi.fn((text: string) => [text]);

vi.mock("./runtime.js", () => ({
  getWeChatRuntime: vi.fn(() => ({
    logging: { shouldLogVerbose: mockShouldLogVerbose },
    channel: {
      media: { saveMediaBuffer: mockSaveMediaBuffer },
      commands: {
        shouldComputeCommandAuthorized: mockShouldComputeCommandAuthorized,
        resolveCommandAuthorizedFromAuthorizers: mockResolveCommandAuthorizedFromAuthorizers,
        isControlCommandMessage: mockIsControlCommandMessage,
      },
      pairing: {
        readAllowFromStore: mockReadAllowFromStore,
        upsertPairingRequest: mockUpsertPairingRequest,
        buildPairingReply: mockBuildPairingReply,
      },
      routing: { resolveAgentRoute: mockResolveAgentRoute },
      session: {
        resolveStorePath: mockResolveStorePath,
        readSessionUpdatedAt: mockReadSessionUpdatedAt,
        recordInboundSession: mockRecordInboundSession,
      },
      reply: {
        resolveEnvelopeFormatOptions: mockResolveEnvelopeFormatOptions,
        formatAgentEnvelope: mockFormatAgentEnvelope,
        finalizeInboundContext: mockFinalizeInboundContext,
        dispatchReplyWithBufferedBlockDispatcher: mockDispatch,
      },
      text: {
        resolveMarkdownTableMode: mockResolveMarkdownTableMode,
        convertMarkdownTables: mockConvertMarkdownTables,
        resolveChunkMode: mockResolveChunkMode,
        chunkMarkdownTextWithMode: mockChunkMarkdownTextWithMode,
      },
    },
  })),
}));

vi.mock("./voice.js", () => ({
  transcribeVoiceMessage: vi.fn().mockResolvedValue("transcribed text"),
}));

vi.mock("./send.js", () => ({
  sendWeChatMessage: vi.fn().mockResolvedValue({ ok: true }),
}));

vi.mock("openclaw/plugin-sdk", () => ({
  createReplyPrefixOptions: vi.fn(() => ({
    onModelSelected: undefined,
  })),
}));

// Mock wechaty — provide Message type enum values
vi.mock("wechaty", () => ({
  WechatyBuilder: { build: vi.fn() },
  types: {
    Message: {
      Unknown: 0,
      Attachment: 1,
      Audio: 2,
      Contact: 3,
      ChatHistory: 4,
      Emoticon: 5,
      Image: 6,
      Text: 7,
      Location: 8,
      MiniProgram: 9,
      GroupNote: 10,
      Transfer: 11,
      RedEnvelope: 12,
      Recalled: 13,
      Url: 14,
      Video: 15,
    },
  },
}));

import { handleWeChatMessage } from "./bot.js";
import { transcribeVoiceMessage } from "./voice.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MSG_TYPE = {
  Unknown: 0,
  Audio: 2,
  Contact: 3,
  Emoticon: 5,
  Image: 6,
  Text: 7,
  Recalled: 13,
  Url: 14,
  Video: 15,
};

function createMockMessage(overrides: Record<string, unknown> = {}) {
  return {
    id: "msg_001",
    self: () => false,
    age: () => 0,
    type: () => MSG_TYPE.Text,
    text: () => "Hello bot",
    room: () => null,
    talker: () => ({
      id: "wxid_sender123",
      name: () => "TestUser",
    }),
    date: () => new Date(1700000000000),
    mentionSelf: vi.fn().mockResolvedValue(false),
    toFileBox: vi.fn().mockResolvedValue({
      toBuffer: vi.fn().mockResolvedValue(Buffer.from("test-media")),
    }),
    toContact: vi.fn().mockResolvedValue({
      name: () => "SharedContact",
      id: "wxid_shared",
    }),
    toUrlLink: vi.fn().mockResolvedValue({
      title: () => "Example",
      url: () => "https://example.com",
    }),
    ...overrides,
  };
}

function createMockAccount(
  configOverrides: Record<string, unknown> = {},
): ResolvedWeChatAccount {
  return {
    accountId: "default",
    enabled: true,
    configured: true,
    puppet: "padlocal",
    padlocalToken: "test_token",
    tokenSource: "config",
    config: {
      dmPolicy: "open",
      allowFrom: [],
      groupPolicy: "allowlist",
      requireMention: true,
      ...configOverrides,
    },
  } as ResolvedWeChatAccount;
}

function createMockBot() {
  const mockSay = vi.fn().mockResolvedValue(undefined);
  return {
    Contact: {
      find: vi.fn().mockResolvedValue({ id: "wxid_sender123", say: mockSay }),
    },
    Room: {
      find: vi.fn().mockResolvedValue({ id: "room_001", say: mockSay }),
    },
    _mockSay: mockSay,
  };
}

function createMockRoom(id = "room_001", topic = "Test Group") {
  return {
    id,
    topic: vi.fn().mockResolvedValue(topic),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("handleWeChatMessage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockReadAllowFromStore.mockResolvedValue([]);
    mockUpsertPairingRequest.mockResolvedValue({ code: "TEST123", created: true });
    mockShouldComputeCommandAuthorized.mockReturnValue(false);
    mockFinalizeInboundContext.mockImplementation((ctx: Record<string, unknown>) => ctx);
  });

  // --- Skipping ---

  it("skips self messages", async () => {
    const msg = createMockMessage({ self: () => true });
    const bot = createMockBot();
    const account = createMockAccount();

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).not.toHaveBeenCalled();
  });

  it("skips stale messages (age > 60s)", async () => {
    const msg = createMockMessage({ age: () => 120 });
    const bot = createMockBot();
    const account = createMockAccount();

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).not.toHaveBeenCalled();
  });

  it("skips empty text messages", async () => {
    const msg = createMockMessage({ text: () => "   " });
    const bot = createMockBot();
    const account = createMockAccount();

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).not.toHaveBeenCalled();
  });

  it("skips Emoticon messages", async () => {
    const msg = createMockMessage({ type: () => MSG_TYPE.Emoticon });
    const bot = createMockBot();
    const account = createMockAccount();

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).not.toHaveBeenCalled();
  });

  it("skips Recalled messages", async () => {
    const msg = createMockMessage({ type: () => MSG_TYPE.Recalled });
    const bot = createMockBot();
    const account = createMockAccount();

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).not.toHaveBeenCalled();
  });

  it("skips Unknown message types", async () => {
    const msg = createMockMessage({ type: () => MSG_TYPE.Unknown });
    const bot = createMockBot();
    const account = createMockAccount();

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).not.toHaveBeenCalled();
  });

  // --- Text DM dispatch ---

  it("dispatches text DM with correct context", async () => {
    const msg = createMockMessage();
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "open" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).toHaveBeenCalledTimes(1);
    expect(mockFinalizeInboundContext).toHaveBeenCalledWith(
      expect.objectContaining({
        RawBody: "Hello bot",
        From: "wechat:wxid_sender123",
        To: "wechat:wxid_sender123",
        ChatType: "direct",
        Provider: "wechat",
        Surface: "wechat",
        SenderId: "wxid_sender123",
        SenderName: "TestUser",
      }),
    );
  });

  it("reports lastInboundAt via statusSink", async () => {
    const msg = createMockMessage();
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "open" });
    const statusSink = vi.fn();

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
      statusSink,
    });

    expect(statusSink).toHaveBeenCalledWith(
      expect.objectContaining({ lastInboundAt: expect.any(Number) }),
    );
  });

  // --- Group message handling ---

  it("skips group message when not @mentioned and requireMention is true", async () => {
    const room = createMockRoom();
    const msg = createMockMessage({
      room: () => room,
      mentionSelf: vi.fn().mockResolvedValue(false),
    });
    const bot = createMockBot();
    const account = createMockAccount({ requireMention: true });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).not.toHaveBeenCalled();
  });

  it("dispatches group message when @mentioned", async () => {
    const room = createMockRoom("room_001", "TestGroup");
    const msg = createMockMessage({
      room: () => room,
      mentionSelf: vi.fn().mockResolvedValue(true),
    });
    const bot = createMockBot();
    const account = createMockAccount({ requireMention: true, dmPolicy: "open" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).toHaveBeenCalledTimes(1);
    expect(mockFinalizeInboundContext).toHaveBeenCalledWith(
      expect.objectContaining({
        ChatType: "group",
        From: "wechat:group:room_001",
        To: "wechat:room_001",
      }),
    );
  });

  it("dispatches group message without mention when requireMention is false", async () => {
    const room = createMockRoom();
    const msg = createMockMessage({ room: () => room });
    const bot = createMockBot();
    const account = createMockAccount({ requireMention: false, dmPolicy: "open" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).toHaveBeenCalledTimes(1);
  });

  it("skips group message when groupPolicy is disabled", async () => {
    const room = createMockRoom();
    const msg = createMockMessage({ room: () => room });
    const bot = createMockBot();
    const account = createMockAccount({ groupPolicy: "disabled" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).not.toHaveBeenCalled();
  });

  // --- DM policy tests ---

  it("blocks DM when dmPolicy is disabled", async () => {
    const msg = createMockMessage();
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "disabled" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).not.toHaveBeenCalled();
  });

  it("sends pairing code when dmPolicy is pairing and sender not allowed", async () => {
    const msg = createMockMessage();
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "pairing", allowFrom: [] });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).not.toHaveBeenCalled();
    expect(mockUpsertPairingRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        channel: "wechat",
        id: "wxid_sender123",
      }),
    );
    expect(bot._mockSay).toHaveBeenCalledWith("Pairing code: TEST123");
  });

  it("does not re-send pairing code when request already exists", async () => {
    mockUpsertPairingRequest.mockResolvedValue({ code: "TEST123", created: false });
    const msg = createMockMessage();
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "pairing", allowFrom: [] });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).not.toHaveBeenCalled();
    expect(bot._mockSay).not.toHaveBeenCalled();
  });

  it("allows DM when dmPolicy is allowlist and sender is in list", async () => {
    const msg = createMockMessage();
    const bot = createMockBot();
    const account = createMockAccount({
      dmPolicy: "allowlist",
      allowFrom: ["wxid_sender123"],
    });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).toHaveBeenCalledTimes(1);
  });

  it("blocks DM when dmPolicy is allowlist and sender not in list", async () => {
    const msg = createMockMessage();
    const bot = createMockBot();
    const account = createMockAccount({
      dmPolicy: "allowlist",
      allowFrom: ["wxid_other"],
    });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).not.toHaveBeenCalled();
  });

  it("allows DM when dmPolicy is open", async () => {
    const msg = createMockMessage();
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "open" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).toHaveBeenCalledTimes(1);
  });

  it("normalizes allowFrom prefixes (wechat:, wx:)", async () => {
    const msg = createMockMessage();
    const bot = createMockBot();
    const account = createMockAccount({
      dmPolicy: "allowlist",
      allowFrom: ["wechat:wxid_sender123"],
    });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).toHaveBeenCalledTimes(1);
  });

  it("wildcard * in allowFrom allows any sender", async () => {
    const msg = createMockMessage();
    const bot = createMockBot();
    const account = createMockAccount({
      dmPolicy: "allowlist",
      allowFrom: ["*"],
    });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).toHaveBeenCalledTimes(1);
  });

  // --- Message type dispatch ---

  it("calls voice transcription for Audio messages", async () => {
    const msg = createMockMessage({ type: () => MSG_TYPE.Audio });
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "open" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(transcribeVoiceMessage).toHaveBeenCalled();
    expect(mockDispatch).toHaveBeenCalledTimes(1);
    expect(mockFinalizeInboundContext).toHaveBeenCalledWith(
      expect.objectContaining({
        RawBody: "[Voice: transcribed text]",
      }),
    );
  });

  it("uses placeholder when voice transcription is disabled", async () => {
    const msg = createMockMessage({ type: () => MSG_TYPE.Audio });
    const bot = createMockBot();
    const account = createMockAccount({
      dmPolicy: "open",
      voice: { transcribe: false },
    });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(transcribeVoiceMessage).not.toHaveBeenCalled();
    expect(mockFinalizeInboundContext).toHaveBeenCalledWith(
      expect.objectContaining({
        RawBody: "[Voice message]",
      }),
    );
  });

  it("uses unavailable placeholder when transcription returns null", async () => {
    vi.mocked(transcribeVoiceMessage).mockResolvedValueOnce(null);
    const msg = createMockMessage({ type: () => MSG_TYPE.Audio });
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "open" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockFinalizeInboundContext).toHaveBeenCalledWith(
      expect.objectContaining({
        RawBody: expect.stringContaining("transcription unavailable"),
      }),
    );
  });

  it("handles Image messages with media save", async () => {
    const msg = createMockMessage({ type: () => MSG_TYPE.Image, text: () => "" });
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "open" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockSaveMediaBuffer).toHaveBeenCalled();
    expect(mockDispatch).toHaveBeenCalledTimes(1);
    expect(mockFinalizeInboundContext).toHaveBeenCalledWith(
      expect.objectContaining({
        MediaPath: "/tmp/test-media.jpg",
        MediaType: "image/jpeg",
      }),
    );
  });

  it("handles Video messages", async () => {
    const msg = createMockMessage({ type: () => MSG_TYPE.Video, text: () => "" });
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "open" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockSaveMediaBuffer).toHaveBeenCalled();
    expect(mockDispatch).toHaveBeenCalledTimes(1);
  });

  it("handles Contact messages", async () => {
    const msg = createMockMessage({ type: () => MSG_TYPE.Contact });
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "open" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).toHaveBeenCalledTimes(1);
    expect(mockFinalizeInboundContext).toHaveBeenCalledWith(
      expect.objectContaining({
        RawBody: "<contact: SharedContact (wxid_shared)>",
      }),
    );
  });

  it("handles Url messages", async () => {
    const msg = createMockMessage({ type: () => MSG_TYPE.Url });
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "open" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockDispatch).toHaveBeenCalledTimes(1);
    expect(mockFinalizeInboundContext).toHaveBeenCalledWith(
      expect.objectContaining({
        RawBody: expect.stringContaining("Example"),
      }),
    );
  });

  // --- Session recording ---

  it("records inbound session", async () => {
    const msg = createMockMessage();
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "open" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockRecordInboundSession).toHaveBeenCalledWith(
      expect.objectContaining({
        storePath: "/tmp/sessions",
        sessionKey: "agent:main:wechat:dm:wxid_sender123",
      }),
    );
  });

  // --- Routing ---

  it("resolves agent route with correct params", async () => {
    const msg = createMockMessage();
    const bot = createMockBot();
    const account = createMockAccount({ dmPolicy: "open" });
    const config = { agents: {} } as never;

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config,
      runtime: {},
    });

    expect(mockResolveAgentRoute).toHaveBeenCalledWith(
      expect.objectContaining({
        channel: "wechat",
        accountId: "default",
        peer: { kind: "direct", id: "wxid_sender123" },
      }),
    );
  });

  it("resolves agent route as group for room messages", async () => {
    const room = createMockRoom("room_001");
    const msg = createMockMessage({
      room: () => room,
      mentionSelf: vi.fn().mockResolvedValue(true),
    });
    const bot = createMockBot();
    const account = createMockAccount({ requireMention: true, dmPolicy: "open" });

    await handleWeChatMessage({
      msg: msg as never,
      bot: bot as never,
      account,
      config: {} as never,
      runtime: {},
    });

    expect(mockResolveAgentRoute).toHaveBeenCalledWith(
      expect.objectContaining({
        peer: { kind: "group", id: "room_001" },
      }),
    );
  });
});
