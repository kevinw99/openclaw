const pw = require("playwright-core");
const fs = require("fs");
const path = require("path");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rdelay = (min, max) => sleep(min + Math.random() * (max - min));
const OUTPUT_DIR = path.join(__dirname, "..", "知识库", "conversations", "doubao");
fs.mkdirSync(OUTPUT_DIR, { recursive: true });
function sanitizeId(s) {
  return s.replace(/[^a-zA-Z0-9_-]/g, "_");
}

(async () => {
  const browser = await pw.chromium.connectOverCDP("http://127.0.0.1:9222");
  const ctx = browser.contexts()[0];
  let page = ctx.pages().find((p) => p.url().includes("doubao")) || (await ctx.newPage());

  console.log("Navigating to doubao.com...");
  await page.goto("https://www.doubao.com/chat/", {
    waitUntil: "domcontentloaded",
    timeout: 20000,
  });
  await sleep(5000);
  console.log("Title:", await page.title(), "URL:", page.url());

  // Check login
  const loggedIn = await page.evaluate(() => {
    const text = document.body.innerText;
    return !text.includes("登录") || text.includes("历史对话");
  });
  if (!loggedIn) {
    console.log("ERROR: Not logged in to Doubao");
    await browser.close();
    return;
  }

  // Count initial conversations
  const initialCount = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a[href*="/chat/"]')).filter((a) =>
      a.href.match(/\/chat\/\d{10,}/),
    ).length;
  });
  console.log("Initial visible conversations:", initialCount);

  // Look for "历史对话" section and try to expand it
  const clicked = await page.evaluate(() => {
    // Find elements with text "历史对话"
    const els = Array.from(document.querySelectorAll("*")).filter(
      (el) => el.textContent.trim() === "历史对话" && el.children.length <= 2,
    );
    if (els.length > 0) {
      els[0].click();
      return "clicked 历史对话";
    }
    return "no 历史对话 element";
  });
  console.log(clicked);
  await sleep(2000);

  // Aggressive sidebar scrolling - find the right scrollable container
  console.log("Scrolling to load all conversations...");
  let maxAttempts = 60;
  let staleCount = 0;
  let prevCount = 0;

  for (let i = 0; i < maxAttempts; i++) {
    const count = await page.evaluate(() => {
      // Find and scroll all potential scrollable containers
      const all = document.querySelectorAll("*");
      for (const el of all) {
        if (
          el.scrollHeight > el.clientHeight + 50 &&
          el.clientHeight > 200 &&
          el.clientHeight < 800
        ) {
          const style = window.getComputedStyle(el);
          if (style.overflowY === "auto" || style.overflowY === "scroll") {
            el.scrollTop = el.scrollHeight;
          }
        }
      }
      return Array.from(document.querySelectorAll('a[href*="/chat/"]')).filter((a) =>
        a.href.match(/\/chat\/\d{10,}/),
      ).length;
    });

    if (count > prevCount) {
      process.stdout.write(count + ".. ");
      staleCount = 0;
    } else {
      staleCount++;
    }
    prevCount = count;
    if (staleCount >= 5) {
      console.log("\nNo more loading after", count, "conversations");
      break;
    }
    await sleep(1200);
  }

  // Collect all unique conversations
  const convs = await page.evaluate(() => {
    const links = document.querySelectorAll('a[href*="/chat/"]');
    const seen = new Set();
    return Array.from(links)
      .map((a) => {
        const m = a.href.match(/\/chat\/(\d{10,})/);
        return { id: m ? m[1] : "", title: a.textContent.trim().slice(0, 200), href: a.href };
      })
      .filter((item) => {
        if (!item.id || seen.has(item.id)) {
          return false;
        }
        seen.add(item.id);
        return true;
      });
  });

  console.log("Found", convs.length, "unique conversations\n");

  // Load existing index to skip already-extracted conversations
  const indexPath = path.join(OUTPUT_DIR, "index.json");
  let existingIndex = [];
  try {
    existingIndex = JSON.parse(fs.readFileSync(indexPath, "utf-8"));
  } catch (_) {}
  const existingIds = new Set(existingIndex.map((e) => e.id));

  const index = [...existingIndex];
  let totalNew = 0;
  let totalMsgs = 0;

  for (let i = 0; i < convs.length; i++) {
    const conv = convs[i];
    const convId = "doubao-" + sanitizeId(conv.id);

    // Skip already extracted
    if (existingIds.has(convId)) {
      continue;
    }

    process.stdout.write(
      "[" + (i + 1) + "/" + convs.length + "] " + conv.title.slice(0, 40) + "... ",
    );

    try {
      await page.goto(conv.href, { waitUntil: "domcontentloaded", timeout: 15000 });
      await rdelay(2000, 4000);
      await page.keyboard.press("Home");
      await sleep(1500);

      const msgs = await page.evaluate(() => {
        const results = [];
        const sels = [
          '[data-testid*="message"]',
          '[class*="message-item"]',
          '[class*="MessageItem"]',
          '[class*="chat-message"]',
          '[class*="turn-"]',
          '[role="article"]',
          "article",
        ];
        let els = [];
        for (const s of sels) {
          const found = Array.from(document.querySelectorAll(s)).filter(
            (el) => el.textContent.trim().length > 5,
          );
          if (found.length >= 2) {
            els = found;
            break;
          }
        }
        if (els.length === 0) {
          const main = document.querySelector(
            "main, [role='main'], [class*='chat-content'], [class*='ChatContent']",
          );
          if (main) {
            els = Array.from(main.querySelectorAll(":scope > div")).filter(
              (d) => d.textContent.trim().length > 10,
            );
          }
        }
        els.forEach((el, idx) => {
          const text = el.textContent.trim();
          if (!text || text.length < 3) {
            return;
          }
          let role = "unknown";
          const cls = (el.className || "").toLowerCase();
          const dr = el.getAttribute("data-role") || el.getAttribute("data-message-role") || "";
          if (dr) {
            role =
              dr.includes("user") || dr.includes("human")
                ? "user"
                : dr.includes("assistant") || dr.includes("bot")
                  ? "assistant"
                  : "unknown";
          } else if (cls.includes("user") || cls.includes("human") || cls.includes("question")) {
            role = "user";
          } else if (
            cls.includes("assistant") ||
            cls.includes("bot") ||
            cls.includes("answer") ||
            cls.includes("response")
          ) {
            role = "assistant";
          } else {
            role = idx % 2 === 0 ? "user" : "assistant";
          }
          const timeEl = el.querySelector("time") || el.querySelector("[class*='time']");
          results.push({
            role,
            content: text.slice(0, 50000),
            timestamp: timeEl?.getAttribute("datetime") || "",
          });
        });
        return results;
      });

      const valid = msgs.filter((m) => m.role !== "unknown" && m.content);
      if (valid.length === 0) {
        console.log("(0 msgs)");
        continue;
      }

      const lines = valid.map((m) =>
        JSON.stringify({
          role: m.role,
          content: m.content,
          timestamp: m.timestamp || new Date().toISOString(),
          content_type: "text",
          message_id: "",
        }),
      );
      fs.writeFileSync(path.join(OUTPUT_DIR, convId + ".jsonl"), lines.join("\n") + "\n");
      index.push({
        id: convId,
        title: conv.title,
        message_count: valid.length,
        platform: "doubao",
      });
      totalNew++;
      totalMsgs += valid.length;
      console.log(valid.length, "msgs");
    } catch (e) {
      console.log("ERR:", e.message.slice(0, 80));
    }
    await rdelay(2500, 5000);
  }

  fs.writeFileSync(indexPath, JSON.stringify(index, null, 2));
  console.log("\n" + "=".repeat(60));
  console.log(
    "Done! Total:",
    index.length,
    "conversations (" + totalNew + " new,",
    totalMsgs,
    "new msgs)",
  );
  await browser.close();
})().catch((e) => console.error("Fatal:", e.message));
