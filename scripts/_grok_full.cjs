const pw = require("playwright-core");
const fs = require("fs");
const path = require("path");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rdelay = (min, max) => sleep(min + Math.random() * (max - min));
const OUTPUT_DIR = path.join(__dirname, "..", "知识库", "conversations", "grok");
fs.mkdirSync(OUTPUT_DIR, { recursive: true });
function sanitizeId(s) {
  return s.replace(/[^a-zA-Z0-9_-]/g, "_");
}

(async () => {
  const browser = await pw.chromium.connectOverCDP("http://127.0.0.1:9222");
  const ctx = browser.contexts()[0];
  let page = ctx.pages()[0] || (await ctx.newPage());

  console.log("Navigating to grok.com...");
  await page.goto("https://grok.com", { waitUntil: "domcontentloaded", timeout: 20000 });
  await sleep(4000);
  console.log("Title:", await page.title(), "URL:", page.url());

  // Click "历史记录" button if visible
  try {
    await page.click('[role="button"]:has-text("历史记录")', { timeout: 3000 });
    await sleep(2000);
    console.log("Clicked 历史记录");
  } catch (_) {}

  // Click "查看全部" button if visible
  try {
    await page.click('button:has-text("查看全部")', { timeout: 3000 });
    await sleep(3000);
    console.log("Clicked 查看全部");
  } catch (_) {
    console.log("No 查看全部 button");
  }

  // Count initial
  const getCount = () =>
    page.evaluate(() => {
      const links = document.querySelectorAll('a[href*="/c/"]');
      const seen = new Set();
      return Array.from(links).filter((a) => {
        const m = a.href.match(/\/c\/([0-9a-f-]{36})/);
        if (!m || seen.has(m[1])) {
          return false;
        }
        seen.add(m[1]);
        return true;
      }).length;
    });

  console.log("Initial conversations:", await getCount());

  // Scroll aggressively to load all history
  console.log("Scrolling to load full history...");
  let staleCount = 0;
  let prevCount = 0;
  for (let i = 0; i < 60; i++) {
    await page.evaluate(() => {
      const containers = document.querySelectorAll("*");
      for (const el of containers) {
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
    });
    await sleep(1200);
    const count = await getCount();
    if (count > prevCount) {
      process.stdout.write(count + ".. ");
      staleCount = 0;
    } else {
      staleCount++;
    }
    prevCount = count;
    if (staleCount >= 5) {
      break;
    }
  }
  console.log("\nFinal count after scrolling:", await getCount());

  // Collect all conversations
  const convs = await page.evaluate(() => {
    const links = document.querySelectorAll('a[href*="/c/"]');
    const seen = new Set();
    return Array.from(links)
      .map((a) => {
        const m = a.href.match(/\/c\/([0-9a-f-]{36})/);
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

  // Load existing index
  const indexPath = path.join(OUTPUT_DIR, "index.json");
  let existingIndex = [];
  try {
    existingIndex = JSON.parse(fs.readFileSync(indexPath, "utf-8"));
  } catch (_) {}
  const existingIds = new Set(existingIndex.map((e) => e.id));
  const index = [...existingIndex];
  let totalNew = 0,
    totalMsgs = 0;

  for (let i = 0; i < convs.length; i++) {
    const conv = convs[i];
    const convId = "grok-" + sanitizeId(conv.id);
    if (existingIds.has(convId)) {
      continue;
    }

    process.stdout.write(
      "[" + (i + 1) + "/" + convs.length + "] " + conv.title.slice(0, 40) + "... ",
    );

    try {
      await page.goto(conv.href, { waitUntil: "domcontentloaded", timeout: 15000 });
      await rdelay(2000, 3500);
      await page.keyboard.press("Home");
      await sleep(1000);

      const msgs = await page.evaluate(() => {
        const results = [];
        const sels = [
          '[data-testid*="message"]',
          '[class*="message"]',
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
          const main = document.querySelector("main, [role='main']");
          if (main) {
            els = Array.from(main.querySelectorAll(":scope > div > div")).filter(
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
          const dr =
            el.getAttribute("data-role") || el.getAttribute("data-message-author-role") || "";
          if (dr) {
            role = dr.includes("user")
              ? "user"
              : dr.includes("assistant") || dr.includes("grok")
                ? "assistant"
                : "unknown";
          } else if (cls.includes("user") || cls.includes("human")) {
            role = "user";
          } else if (
            cls.includes("assistant") ||
            cls.includes("bot") ||
            cls.includes("grok") ||
            cls.includes("model")
          ) {
            role = "assistant";
          } else {
            role = idx % 2 === 0 ? "user" : "assistant";
          }
          const timeEl = el.querySelector("time");
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
      index.push({ id: convId, title: conv.title, message_count: valid.length, platform: "grok" });
      totalNew++;
      totalMsgs += valid.length;
      console.log(valid.length, "msgs");
    } catch (e) {
      console.log("ERR:", e.message.slice(0, 80));
    }
    await rdelay(1500, 3000);
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
