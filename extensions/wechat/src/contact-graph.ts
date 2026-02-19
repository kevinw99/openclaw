import type { Wechaty, Contact, Room } from "wechaty";
import { writeFileSync, readFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

export type ContactNode = {
  wxid: string;
  displayName: string;
  remark: string;
  tags: string[];
  sharedGroupIds: string[];
  sharedGroupNames: string[];
  lastMessageAt?: number;
};

const contactIndices = new Map<string, ContactNode[]>();

function getContactStorePath(accountId: string): string {
  const dir = join(homedir(), ".openclaw", "credentials", "wechat", accountId);
  mkdirSync(dir, { recursive: true });
  return join(dir, "contacts.json");
}

/**
 * Build a contact index from the bot's contact and room lists.
 * Persisted to ~/.openclaw/credentials/wechat/<accountId>/contacts.json
 */
export async function buildContactIndex(
  bot: Wechaty,
  accountId: string,
): Promise<ContactNode[]> {
  const contacts: Contact[] = await bot.Contact.findAll();
  const rooms: Room[] = await bot.Room.findAll();

  // Build room membership map
  const roomMembership = new Map<string, { roomId: string; roomName: string }[]>();
  for (const room of rooms) {
    let topic = "";
    try {
      topic = (await room.topic()) || room.id;
    } catch {
      topic = room.id;
    }
    let members: Contact[] = [];
    try {
      members = await room.memberAll();
    } catch {
      continue;
    }
    for (const member of members) {
      const existing = roomMembership.get(member.id) ?? [];
      existing.push({ roomId: room.id, roomName: topic });
      roomMembership.set(member.id, existing);
    }
  }

  const nodes: ContactNode[] = [];
  for (const contact of contacts) {
    if (contact.self()) {
      continue;
    }
    const wxid = contact.id;
    const displayName = contact.name() ?? "";
    // Wechaty Contact may expose alias() for remark
    let remark = "";
    try {
      remark = (await (contact as { alias?: () => Promise<string> }).alias?.()) ?? "";
    } catch {
      // not all puppets support alias
    }

    const memberOf = roomMembership.get(wxid) ?? [];

    nodes.push({
      wxid,
      displayName,
      remark,
      tags: [],
      sharedGroupIds: memberOf.map((r) => r.roomId),
      sharedGroupNames: memberOf.map((r) => r.roomName),
    });
  }

  contactIndices.set(accountId, nodes);

  // Persist to disk
  try {
    const storePath = getContactStorePath(accountId);
    writeFileSync(storePath, JSON.stringify(nodes, null, 2), "utf8");
  } catch (err) {
    console.error(`[wechat] Failed to persist contact index: ${String(err)}`);
  }

  return nodes;
}

/**
 * Search the contact index for a given account.
 * Falls back to loading from disk if not in memory.
 */
export function searchContacts(query: string, accountId: string): ContactNode[] {
  let nodes = contactIndices.get(accountId);
  if (!nodes) {
    try {
      const storePath = getContactStorePath(accountId);
      const raw = readFileSync(storePath, "utf8");
      nodes = JSON.parse(raw) as ContactNode[];
      contactIndices.set(accountId, nodes);
    } catch {
      return [];
    }
  }

  if (!query?.trim()) {
    return nodes;
  }

  const q = query.toLowerCase();
  return nodes.filter(
    (node) =>
      node.displayName.toLowerCase().includes(q) ||
      node.remark.toLowerCase().includes(q) ||
      node.wxid.toLowerCase().includes(q) ||
      node.sharedGroupNames.some((name) => name.toLowerCase().includes(q)),
  );
}
