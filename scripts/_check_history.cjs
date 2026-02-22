// Check Grok and Doubao for full conversation history
const pw = require("playwright-core");
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await pw.chromium.connectOverCDP("http://127.0.0.1:9222");
  const ctx = browser.contexts()[0];

  // === GROK ===
  console.log("=== GROK ===");
  let page = ctx.pages()[0] || await ctx.newPage();
  await page.goto("https://grok.com", { waitUntil: "domcontentloaded", timeout: 15000 });
  await sleep(3000);

  // Click "历史记录" or "History" to open full history panel
  const grokButtons = await page.evaluate(() => {
    return Array.from(document.querySelectorAll("button, [role='button'], a")).map(el => ({
      tag: el.tagName, text: el.textContent.trim().slice(0, 60), href: el.href || "",
    })).filter(b =>
      b.text.includes("历史") || b.text.includes("History") || b.text.includes("查看全部") ||
      b.text.includes("View all") || b.text.includes("More") || b.text.includes("更多") ||
      b.text.includes("Older") || b.href.includes("history")
    );
  });
  console.log("Grok history-related buttons:", JSON.stringify(grokButtons, null, 2));

  // Count current visible conversations
  const grokCount = await page.evaluate(() => {
    return document.querySelectorAll('a[href*="/c/"]').length;
  });
  console.log("Grok visible conversations:", grokCount);

  // Try clicking "查看全部" or "历史记录"
  try {
    await page.click('button:has-text("查看全部")', { timeout: 3000 });
    await sleep(3000);
    console.log("Clicked 查看全部");
  } catch(e) {
    try {
      await page.click('[role="button"]:has-text("历史记录")', { timeout: 3000 });
      await sleep(3000);
      console.log("Clicked 历史记录");
    } catch(e2) {
      console.log("No history expand button found");
    }
  }

  // Scroll aggressively in sidebar/history panel
  for (let i = 0; i < 30; i++) {
    const prev = await page.evaluate(() => document.querySelectorAll('a[href*="/c/"]').length);
    await page.evaluate(() => {
      // Try scrolling multiple potential containers
      const containers = document.querySelectorAll("nav, aside, [class*='sidebar'], [class*='history'], [class*='scroll']");
      containers.forEach(c => c.scrollTop = c.scrollHeight);
      // Also try the main scrollable area
      document.querySelector("[style*='overflow']")?.scrollTo(0, 999999);
    });
    await sleep(1500);
    const now = await page.evaluate(() => document.querySelectorAll('a[href*="/c/"]').length);
    if (now > prev) process.stdout.write(now + ".. ");
    else { console.log("\nStopped at", now); break; }
  }

  const grokFinal = await page.evaluate(() => {
    const links = document.querySelectorAll('a[href*="/c/"]');
    const seen = new Set();
    return Array.from(links).filter(a => {
      const m = a.href.match(/\/c\/([0-9a-f-]{36})/);
      if (!m || seen.has(m[1])) return false;
      seen.add(m[1]);
      return true;
    }).length;
  });
  console.log("Grok unique conversations after scroll:", grokFinal);

  // Check if there's a dedicated history page
  const grokHistoryLink = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll("a"));
    return links.filter(a => a.href.includes("history")).map(a => a.href);
  });
  console.log("Grok history page links:", grokHistoryLink);

  // === DOUBAO ===
  console.log("\n=== DOUBAO ===");
  await page.goto("https://www.doubao.com/chat/", { waitUntil: "domcontentloaded", timeout: 15000 });
  await sleep(5000);

  const doubaoButtons = await page.evaluate(() => {
    return Array.from(document.querySelectorAll("button, [role='button'], a, div")).map(el => ({
      tag: el.tagName, text: el.textContent.trim().slice(0, 60),
      href: el.href || "", cls: (el.className || "").slice(0, 60),
    })).filter(b =>
      b.text === "历史对话" || b.text === "更多" || b.text === "查看更多" ||
      b.text === "加载更多" || b.text.includes("全部对话") || b.text.includes("所有对话") ||
      b.href.includes("history")
    );
  });
  console.log("Doubao history buttons:", JSON.stringify(doubaoButtons, null, 2));

  const doubaoCount = await page.evaluate(() => {
    const links = document.querySelectorAll('a[href*="/chat/"]');
    return Array.from(links).filter(a => a.href.match(/\/chat\/\d{10,}/)).length;
  });
  console.log("Doubao visible conversations:", doubaoCount);

  // Scroll sidebar aggressively
  for (let i = 0; i < 50; i++) {
    const prev = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('a[href*="/chat/"]')).filter(a => a.href.match(/\/chat\/\d{10,}/)).length;
    });
    await page.evaluate(() => {
      const containers = document.querySelectorAll("nav, aside, [class*='sidebar'], [class*='Sidebar'], [class*='scroll'], [class*='list']");
      containers.forEach(c => { if (c.scrollHeight > c.clientHeight) c.scrollTop = c.scrollHeight; });
    });
    await sleep(1200);
    const now = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('a[href*="/chat/"]')).filter(a => a.href.match(/\/chat\/\d{10,}/)).length;
    });
    if (now > prev) process.stdout.write(now + ".. ");
    else { console.log("\nStopped at", now); break; }
  }

  const doubaoFinal = await page.evaluate(() => {
    const links = document.querySelectorAll('a[href*="/chat/"]');
    const seen = new Set();
    return Array.from(links).filter(a => {
      const m = a.href.match(/\/chat\/(\d{10,})/);
      if (!m || seen.has(m[1])) return false;
      seen.add(m[1]);
      return true;
    }).length;
  });
  console.log("Doubao unique conversations after scroll:", doubaoFinal);

  await browser.close();
})().catch(e => console.error("Fatal:", e.message));
