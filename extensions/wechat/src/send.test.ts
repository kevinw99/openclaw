import { describe, expect, it } from "vitest";
import { chunkText } from "./send.js";

describe("chunkText", () => {
  it("returns empty array for empty text", () => {
    expect(chunkText("", 2000)).toEqual([]);
  });

  it("returns single chunk for short text", () => {
    expect(chunkText("hello", 2000)).toEqual(["hello"]);
  });

  it("returns single chunk when text equals limit", () => {
    const text = "a".repeat(2000);
    expect(chunkText(text, 2000)).toEqual([text]);
  });

  it("splits on newline boundary", () => {
    const line1 = "a".repeat(100);
    const line2 = "b".repeat(100);
    const text = `${line1}\n${line2}`;
    const chunks = chunkText(text, 110);
    expect(chunks.length).toBeGreaterThanOrEqual(2);
    expect(chunks[0]).toBe(line1);
    expect(chunks[1]).toBe(line2);
  });

  it("splits on space boundary when no newline", () => {
    const word1 = "a".repeat(50);
    const word2 = "b".repeat(50);
    const text = `${word1} ${word2}`;
    const chunks = chunkText(text, 60);
    expect(chunks.length).toBe(2);
    expect(chunks[0]).toBe(word1);
    expect(chunks[1]).toBe(word2);
  });

  it("force-breaks when no whitespace", () => {
    const text = "a".repeat(150);
    const chunks = chunkText(text, 100);
    expect(chunks.length).toBe(2);
    expect(chunks[0]).toBe("a".repeat(100));
    expect(chunks[1]).toBe("a".repeat(50));
  });

  it("handles limit <= 0 by returning whole text", () => {
    expect(chunkText("hello", 0)).toEqual(["hello"]);
    expect(chunkText("hello", -1)).toEqual(["hello"]);
  });
});
