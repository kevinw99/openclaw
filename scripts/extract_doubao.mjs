#!/usr/bin/env node
/**
 * Doubao (豆包) conversation extractor - standalone Playwright script
 *
 * Connects to your Chrome via CDP to reuse your login session.
 * Uses extended delays to avoid Bytedance anti-bot detection.
 *
 * Usage:
 *   1. Quit Chrome completely
 *   2. node scripts/extract_doubao.mjs
 *
 * Or connect to already-running Chrome:
 *   1. Launch Chrome with: /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
 *   2. node scripts/extract_doubao.mjs --cdp ws://127.0.0.1:9222
 */

import { chromium } from 'playwright-core';
import { writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..');
const OUTPUT_DIR = join(PROJECT_ROOT, '知识库', 'conversations', 'doubao');

const args = process.argv.slice(2);
let cdpUrl = args.includes('--cdp') ? args[args.indexOf('--cdp') + 1] : null;

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// Longer delays for Doubao anti-bot
function randomDelay(min = 2000, max = 5000) {
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

    console.log('\nNavigating to doubao.com...');
    await page.goto('https://www.doubao.com', { waitUntil: 'networkidle', timeout: 30000 });
    await randomDelay(3000, 6000);

    const pageTitle = await page.title();
    console.log(`Page title: ${pageTitle}`);

    // Get conversation list
    console.log('\nExtracting conversation list...');
    const getConversations = async () => {
      return page.evaluate(() => {
        const selectors = [
          'a[href*="/chat/"]',
          '[data-testid*="conversation"]',
          '[class*="session-item"]',
          '[class*="SessionItem"]',
          '[class*="chat-item"]',
          '[class*="conversation-item"]',
        ];

        let elements = [];
        for (const sel of selectors) {
          elements = document.querySelectorAll(sel);
          if (elements.length > 0) break;
        }

        const seen = new Set();
        return Array.from(elements)
          .map(el => {
            const link = el.tagName === 'A' ? el : el.querySelector('a') || el.closest('a');
            const href = link?.href || '';
            const idMatch = href.match(/\/chat\/([^/?#]+)/);
            const id = idMatch?.[1] || el.getAttribute('data-id') ||
                       el.getAttribute('data-session-id') || '';
            const title = el.textContent.trim().slice(0, 200);
            return { id, title, href };
          })
          .filter(item => {
            const key = item.id || item.title;
            if (!key || seen.has(key)) return false;
            seen.add(key);
            return true;
          });
      });
    };

    let conversations = await getConversations();
    console.log(`Found ${conversations.length} conversations`);

    if (conversations.length === 0) {
      console.log('\nNo conversations found. Possible reasons:');
      console.log('  - Not logged in to doubao.com');
      console.log('  - UI structure has changed');
      console.log('  - Page hasn\'t fully loaded');

      const ssPath = join(OUTPUT_DIR, 'debug-screenshot.png');
      mkdirSync(dirname(ssPath), { recursive: true });
      await page.screenshot({ path: ssPath, fullPage: true });
      console.log(`  Screenshot saved: ${ssPath}`);

      if (shouldClose) await context.close();
      return;
    }

    // Scroll sidebar for more
    console.log('Scrolling sidebar...');
    let prevCount = conversations.length;
    for (let scroll = 0; scroll < 20; scroll++) {
      await page.evaluate(() => {
        const sidebar = document.querySelector('nav, aside, [class*="sidebar"], [class*="Sidebar"]');
        if (sidebar) sidebar.scrollTop = sidebar.scrollHeight;
      });
      await randomDelay(1500, 3000);
      const current = await getConversations();
      if (current.length === prevCount) break;
      prevCount = current.length;
    }

    conversations = await getConversations();
    console.log(`Total conversations: ${conversations.length}`);

    // Extract each conversation
    mkdirSync(OUTPUT_DIR, { recursive: true });
    const index = [];
    let totalMessages = 0;

    for (let i = 0; i < conversations.length; i++) {
      const conv = conversations[i];
      process.stdout.write(`  [${i + 1}/${conversations.length}] ${conv.title.slice(0, 40)}... `);

      try {
        const url = conv.href || `https://www.doubao.com/chat/${conv.id}`;
        await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
        await randomDelay(2000, 4000);

        await page.keyboard.press('Home');
        await randomDelay(1000, 2000);

        // Extract messages
        const messages = await page.evaluate(() => {
          const msgs = [];
          const selectors = [
            '[data-testid*="message"]',
            '[class*="message-item"]',
            '[class*="MessageItem"]',
            '[class*="chat-message"]',
            '[class*="turn-"]',
            '[role="article"]',
          ];

          let elements = [];
          for (const sel of selectors) {
            elements = document.querySelectorAll(sel);
            if (elements.length > 0) break;
          }

          if (elements.length === 0) {
            const chatArea = document.querySelector('[class*="chat-content"]') ||
                             document.querySelector('[class*="ChatContent"]') ||
                             document.querySelector('main');
            if (chatArea) {
              elements = chatArea.querySelectorAll(':scope > div');
            }
          }

          elements.forEach((el, idx) => {
            const text = el.textContent.trim();
            if (!text || text.length < 2) return;

            let role = 'unknown';
            const cls = (el.className || '').toLowerCase();
            const dataRole = el.getAttribute('data-role') ||
                             el.getAttribute('data-message-role') || '';

            if (dataRole) {
              role = dataRole.includes('user') || dataRole.includes('human') ? 'user' :
                     dataRole.includes('assistant') || dataRole.includes('bot') ? 'assistant' : 'unknown';
            } else if (cls.includes('user') || cls.includes('human') || cls.includes('question')) {
              role = 'user';
            } else if (cls.includes('assistant') || cls.includes('bot') ||
                       cls.includes('answer') || cls.includes('response')) {
              role = 'assistant';
            } else {
              role = idx % 2 === 0 ? 'user' : 'assistant';
            }

            const timeEl = el.querySelector('time') || el.querySelector('[class*="time"]');
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

        const convId = `doubao-${sanitizeId(conv.id || String(i))}`;
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
          platform: 'doubao',
        });

        totalMessages += validMessages.length;
        console.log(`${validMessages.length} msgs`);

      } catch (err) {
        console.log(`ERROR: ${err.message.slice(0, 80)}`);
      }

      // Extended delay for Doubao anti-bot
      await randomDelay(3000, 7000);
    }

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
