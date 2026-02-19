import { describe, expect, it, vi, beforeEach } from "vitest";

// Mock fs to prevent actual disk I/O
vi.mock("node:fs", () => ({
  writeFileSync: vi.fn(),
  readFileSync: vi.fn(() => {
    throw new Error("ENOENT");
  }),
  mkdirSync: vi.fn(),
}));

import { buildContactIndex, searchContacts } from "./contact-graph.js";

function createMockContact(id: string, name: string, opts: { self?: boolean } = {}) {
  return {
    id,
    name: () => name,
    self: () => opts.self ?? false,
    alias: vi.fn().mockResolvedValue(""),
  };
}

function createMockRoom(id: string, topic: string, memberIds: string[]) {
  return {
    id,
    topic: vi.fn().mockResolvedValue(topic),
    memberAll: vi.fn().mockResolvedValue(
      memberIds.map((mid) => ({ id: mid })),
    ),
  };
}

function createMockBot(contacts: ReturnType<typeof createMockContact>[], rooms: ReturnType<typeof createMockRoom>[]) {
  return {
    Contact: {
      findAll: vi.fn().mockResolvedValue(contacts),
    },
    Room: {
      findAll: vi.fn().mockResolvedValue(rooms),
    },
  };
}

describe("buildContactIndex", () => {
  it("indexes contacts with display names", async () => {
    const contacts = [
      createMockContact("wxid_alice", "Alice"),
      createMockContact("wxid_bob", "Bob"),
    ];
    const bot = createMockBot(contacts, []);

    const nodes = await buildContactIndex(bot as never, "test-account");

    expect(nodes).toHaveLength(2);
    expect(nodes[0].wxid).toBe("wxid_alice");
    expect(nodes[0].displayName).toBe("Alice");
    expect(nodes[1].wxid).toBe("wxid_bob");
  });

  it("excludes self contact", async () => {
    const contacts = [
      createMockContact("wxid_self", "Me", { self: true }),
      createMockContact("wxid_alice", "Alice"),
    ];
    const bot = createMockBot(contacts, []);

    const nodes = await buildContactIndex(bot as never, "test-account");

    expect(nodes).toHaveLength(1);
    expect(nodes[0].wxid).toBe("wxid_alice");
  });

  it("includes shared group info in contact nodes", async () => {
    const contacts = [createMockContact("wxid_alice", "Alice")];
    const rooms = [createMockRoom("room_001", "Work Chat", ["wxid_alice"])];
    const bot = createMockBot(contacts, rooms);

    const nodes = await buildContactIndex(bot as never, "test-account");

    expect(nodes[0].sharedGroupIds).toEqual(["room_001"]);
    expect(nodes[0].sharedGroupNames).toEqual(["Work Chat"]);
  });
});

describe("searchContacts", () => {
  beforeEach(async () => {
    // Populate index via buildContactIndex
    const contacts = [
      createMockContact("wxid_alice", "Alice"),
      createMockContact("wxid_bob", "Bob Zhang"),
      createMockContact("wxid_carol", "Carol"),
    ];
    const rooms = [
      createMockRoom("room_dev", "Dev Team", ["wxid_alice", "wxid_bob"]),
    ];
    const bot = createMockBot(contacts, rooms);
    await buildContactIndex(bot as never, "search-test");
  });

  it("returns all contacts for empty query", () => {
    const results = searchContacts("", "search-test");
    expect(results).toHaveLength(3);
  });

  it("searches by display name", () => {
    const results = searchContacts("alice", "search-test");
    expect(results).toHaveLength(1);
    expect(results[0].wxid).toBe("wxid_alice");
  });

  it("searches by wxid", () => {
    const results = searchContacts("wxid_bob", "search-test");
    expect(results).toHaveLength(1);
    expect(results[0].displayName).toBe("Bob Zhang");
  });

  it("searches by shared group name", () => {
    const results = searchContacts("Dev Team", "search-test");
    expect(results).toHaveLength(2);
  });

  it("is case insensitive", () => {
    const results = searchContacts("CAROL", "search-test");
    expect(results).toHaveLength(1);
    expect(results[0].wxid).toBe("wxid_carol");
  });

  it("returns empty for unknown account", () => {
    const results = searchContacts("alice", "nonexistent-account");
    expect(results).toEqual([]);
  });

  it("returns empty when query matches nothing", () => {
    const results = searchContacts("zzzzz", "search-test");
    expect(results).toEqual([]);
  });
});
