import type { Message } from "wechaty";
import { execSync } from "node:child_process";
import { readFileSync, writeFileSync, unlinkSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import type { WeChatVoiceConfig } from "./types.js";

/**
 * Transcribe a Wechaty voice message to text.
 *
 * WeChat voice messages use SILK codec. Transcription flow:
 * - openai: SILK → MP3 (via ffmpeg) → Whisper API
 * - system: macOS Speech framework (stub — logs warning on non-macOS)
 * - disabled: returns null
 */
export async function transcribeVoiceMessage(
  msg: Message,
  config: WeChatVoiceConfig,
): Promise<string | null> {
  if (config.transcribe === false) {
    return null;
  }

  const provider = config.provider ?? "system";

  try {
    const fileBox = await msg.toFileBox();
    const buffer = await fileBox.toBuffer();

    const tempDir = mkdtempSync(join(tmpdir(), "wechat-voice-"));
    const silkPath = join(tempDir, "voice.silk");
    writeFileSync(silkPath, buffer);

    try {
      if (provider === "openai") {
        return await transcribeWithOpenAI(silkPath, config.openaiApiKey, tempDir);
      }
      return await transcribeWithSystem(silkPath, tempDir);
    } finally {
      // Clean up temp files
      try {
        unlinkSync(silkPath);
        const mp3Path = join(tempDir, "voice.mp3");
        try {
          unlinkSync(mp3Path);
        } catch {
          // may not exist
        }
      } catch {
        // ignore cleanup errors
      }
    }
  } catch {
    return null;
  }
}

async function transcribeWithOpenAI(
  silkPath: string,
  apiKey: string | undefined,
  tempDir: string,
): Promise<string | null> {
  if (!apiKey) {
    console.warn("[wechat] OpenAI voice transcription requires openaiApiKey in voice config");
    return null;
  }

  // Convert SILK to MP3 via ffmpeg
  const mp3Path = join(tempDir, "voice.mp3");
  try {
    execSync(`ffmpeg -i "${silkPath}" -y "${mp3Path}" 2>/dev/null`, { timeout: 30000 });
  } catch {
    console.warn("[wechat] ffmpeg conversion failed — is ffmpeg installed?");
    return null;
  }

  // Call Whisper API
  const audioBuffer = readFileSync(mp3Path);
  const blob = new Blob([audioBuffer], { type: "audio/mpeg" });
  const formData = new FormData();
  formData.append("file", blob, "voice.mp3");
  formData.append("model", "whisper-1");

  const response = await fetch("https://api.openai.com/v1/audio/transcriptions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
    body: formData,
  });

  if (!response.ok) {
    console.warn(`[wechat] Whisper API error: ${response.status}`);
    return null;
  }

  const result = (await response.json()) as { text?: string };
  return result.text?.trim() || null;
}

async function transcribeWithSystem(
  silkPath: string,
  _tempDir: string,
): Promise<string | null> {
  // macOS-only: use Speech.framework
  if (process.platform !== "darwin") {
    console.warn("[wechat] System voice transcription is only available on macOS");
    return null;
  }

  // Convert SILK to a format macOS can handle
  const mp3Path = join(_tempDir, "voice.mp3");
  try {
    execSync(`ffmpeg -i "${silkPath}" -y "${mp3Path}" 2>/dev/null`, { timeout: 30000 });
  } catch {
    console.warn("[wechat] ffmpeg conversion failed — is ffmpeg installed?");
    return null;
  }

  // Stub: macOS Speech.framework integration
  // In a full implementation, this would call a Swift helper or use NSSpeechRecognizer
  console.warn("[wechat] System voice transcription not yet implemented — use openai provider");
  return null;
}
