#!/usr/bin/env node
/**
 * Grok conversation extractor - standalone Playwright script
 *
 * Connects to your Chrome via CDP (remote debugging) to reuse your login session.
 *
 * Usage:
 *   1. Quit Chrome completely
 *   2. node scripts/extract_grok.mjs
 *      (script launches Chrome with debugging, extracts, then outputs JSONL)
 *
 * Or connect to already-running Chrome:
 *   1. Launch Chrome with: /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
 *   2. node scripts/extract_grok.mjs --cdp ws://127.0.0.1:9222
 */

import { chromium } from 'playwright-core';
import { writeFileSync, mkdirSync, readFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..');
const OUTPUT_DIR = join(PROJECT_ROOT, '知识库', 'conversations', 'grok');

// Parse args
const args = process.argv.slice(2);
let cdpUrl = args.includes('--cdp') ? args[args.indexOf('--cdp') + 1] : null;
const headless = args.includes('--headless');

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function randomDelay(min = 1000, max = 3000) {
  return sleep(min + Math.random() * (max - min));
}

function sanitizeId(s) {
  return s.replace(/[^a-zA-Z0-9_-]/g, '_');
}

async function main() {
  let browser, context, shouldClose = false;

  try {
    // Auto-detect Chrome debugging port if not specified
    if (!cdpUrl) {
      try {
        const resp = await fetch('http://127.0.0.1:9222/json/version');
        if (resp.ok) {
          const info = await resp.json();
          cdpUrl = info.webSocketDebuggerUrl;
          console.log('Auto-detected Chrome debugging on port 9222');
        }
      } catch (_) {}
    }

    if (cdpUrl) {
      console.log(`Connecting to Chrome via CDP: ${cdpUrl}`);
      browser = await chromium.connectOverCDP(cdpUrl);
      context = browser.contexts()[0];
    } else {
      console.error('Chrome is not running with remote debugging enabled.');
      console.error('');
      console.error('Run this first:');
      console.error('  ./scripts/chrome-debug.sh');
      console.error('');
      console.error('Or manually:');
      console.error('  1. Quit Chrome');
      console.error('  2. /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222');
      console.error('  3. Re-run this script');
      process.exit(1);
    }

    const page = context.pages()[0] || await context.newPage();

    // Navigate to Grok
    console.log('\nNavigating to grok.com...');
    await page.goto('https://grok.com', { waitUntil: 'networkidle', timeout: 30000 });
    await randomDelay(2000, 4000);

    // Check if logged in
    const pageTitle = await page.title();
    console.log(`Page title: ${pageTitle}`);

    // Get conversation list from sidebar
    console.log('\nExtracting conversation list from sidebar...');
    const conversations = await page.evaluate(() => {
      // Try multiple selectors for sidebar conversation links
      const selectors = [
        'a[href*="/chat/"]',
        'nav a[href*="/conversation/"]',
        '[data-testid*="conversation"] a',
        'aside a[href*="/"]',
      ];

      let links = [];
      for (const sel of selectors) {
        const found = document.querySelectorAll(sel);
        if (found.length > 0) {
          links = Array.from(found);
          break;
        }
      }

      // Deduplicate and extract
      const seen = new Set();
      return links
        .map(a => {
          const href = a.href;
          const match = href.match(/\/chat\/([^/?#]+)/);
          const id = match?.[1] || '';
          const title = a.textContent.trim().slice(0, 200);
          return { id, title, href };
        })
        .filter(item => {
          if (!item.id || seen.has(item.id)) return false;
          seen.add(item.id);
          return true;
        });
    });

    console.log(`Found ${conversations.length} conversations`);

    if (conversations.length === 0) {
      console.log('\nNo conversations found. Possible reasons:');
      console.log('  - Not logged in to grok.com');
      console.log('  - UI structure has changed');
      console.log('  - Page hasn\'t fully loaded');

      // Take screenshot for debugging
      const ssPath = join(OUTPUT_DIR, 'debug-screenshot.png');
      mkdirSync(dirname(ssPath), { recursive: true });
      await page.screenshot({ path: ssPath, fullPage: true });
      console.log(`  Screenshot saved: ${ssPath}`);

      if (shouldClose) await context.close();
      return;
    }

    // Scroll sidebar to load all conversations
    console.log('Scrolling sidebar to load all conversations...');
    let prevCount = conversations.length;
    for (let scroll = 0; scroll < 20; scroll++) {
      await page.evaluate(() => {
        const sidebar = document.querySelector('nav, aside, [class*="sidebar"]');
        if (sidebar) sidebar.scrollTop = sidebar.scrollHeight;
      });
      await randomDelay(1000, 2000);

      const newConvs = await page.evaluate(() => {
        const links = document.querySelectorAll('a[href*="/chat/"]');
        return links.length;
      });
      if (newConvs === prevCount) break;
      prevCount = newConvs;
    }

    // Re-fetch after scrolling
    const allConversations = await page.evaluate(() => {
      const links = document.querySelectorAll('a[href*="/chat/"]');
      const seen = new Set();
      return Array.from(links)
        .map(a => {
          const match = a.href.match(/\/chat\/([^/?#]+)/);
          return {
            id: match?.[1] || '',
            title: a.textContent.trim().slice(0, 200),
            href: a.href,
          };
        })
        .filter(item => {
          if (!item.id || seen.has(item.id)) return false;
          seen.add(item.id);
          return true;
        });
    });

    console.log(`Total conversations after scrolling: ${allConversations.length}`);

    // Extract each conversation
    mkdirSync(OUTPUT_DIR, { recursive: true });
    const index = [];
    let totalMessages = 0;

    for (let i = 0; i < allConversations.length; i++) {
      const conv = allConversations[i];
      process.stdout.write(`  [${i + 1}/${allConversations.length}] ${conv.title.slice(0, 40)}... `);

      try {
        await page.goto(conv.href, { waitUntil: 'networkidle', timeout: 20000 });
        await randomDelay(1500, 3000);

        // Scroll to top to load all messages
        await page.keyboard.press('Home');
        await randomDelay(1000, 2000);

        // Extract messages
        const messages = await page.evaluate(() => {
          const msgs = [];
          // Try multiple message container selectors
          const selectors = [
            '[data-testid*="message"]',
            '[class*="message-row"]',
            '[class*="MessageRow"]',
            '[role="article"]',
            '.message',
          ];

          let elements = [];
          for (const sel of selectors) {
            elements = document.querySelectorAll(sel);
            if (elements.length > 0) break;
          }

          // Fallback: look for turn-based structure in main area
          if (elements.length === 0) {
            const main = document.querySelector('main, [role="main"]');
            if (main) {
              elements = main.querySelectorAll(':scope > div > div');
            }
          }

          elements.forEach((el, idx) => {
            const text = el.textContent.trim();
            if (!text || text.length < 2) return;

            let role = 'unknown';
            const cls = el.className || '';
            const dataRole = el.getAttribute('data-role') || el.getAttribute('data-message-author-role') || '';

            if (dataRole) {
              role = dataRole.includes('user') ? 'user' :
                     dataRole.includes('assistant') || dataRole.includes('grok') ? 'assistant' : 'unknown';
            } else if (cls.includes('user') || cls.includes('human')) {
              role = 'user';
            } else if (cls.includes('assistant') || cls.includes('bot') || cls.includes('grok')) {
              role = 'assistant';
            } else {
              role = idx % 2 === 0 ? 'user' : 'assistant';
            }

            const timeEl = el.querySelector('time');
            const timestamp = timeEl?.getAttribute('datetime') || '';

            msgs.push({ role, content: text.slice(0, 50000), timestamp });
          });

          return msgs;
        });

        const validMessages = messages.filter(m => m.role !== 'unknown' && m.content);

        if (validMessages.length === 0) {
          console.log('(no messages)');
          continue;
        }

        // Write JSONL
        const convId = `grok-${sanitizeId(conv.id)}`;
        const jsonlPath = join(OUTPUT_DIR, `${convId}.jsonl`);
        const lines = validMessages.map(m => JSON.stringify({
          role: m.role,
          content: m.content,
          timestamp: m.timestamp || new Date().toISOString(),
          content_type: 'text',
          message_id: '',
        }));
        writeFileSync(jsonlPath, lines.join('\n') + '\n');

        index.push({
          id: convId,
          title: conv.title,
          message_count: validMessages.length,
          platform: 'grok',
        });

        totalMessages += validMessages.length;
        console.log(`${validMessages.length} msgs`);

      } catch (err) {
        console.log(`ERROR: ${err.message.slice(0, 80)}`);
      }

      // Rate limit
      await randomDelay(2000, 5000);
    }

    // Write index
    writeFileSync(join(OUTPUT_DIR, 'index.json'), JSON.stringify(index, null, 2));

    console.log(`\n${'='.repeat(60)}`);
    console.log(`Done! ${index.length} conversations, ${totalMessages} messages`);
    console.log(`Output: ${OUTPUT_DIR}`);

  } catch (err) {
    console.error('Fatal error:', err.message);
    process.exit(1);
  } finally {
    if (shouldClose && context) {
      await context.close().catch(() => {});
    }
  }
}

main();
