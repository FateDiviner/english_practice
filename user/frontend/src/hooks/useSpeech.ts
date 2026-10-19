import { useCallback, useEffect, useMemo, useState } from "react";
import { useAppStore } from "@/stores/app";

/** 浏览器是否支持语音合成 */
export function isSpeechSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

interface SpeakOptions {
  accent: "en-GB" | "en-US";
  rate: number;
}

/**
 * 选择最匹配目标口音的音色。
 * 优先级：lang 精确匹配 > lang 前缀匹配 > 任意英文音色。
 */
function pickVoice(accent: "en-GB" | "en-US", voices: SpeechSynthesisVoice[]) {
  if (!voices.length) return null;
  const exact = voices.find((voice) => voice.lang.replace("_", "-") === accent);
  if (exact) return exact;
  const prefix = voices.find((voice) => voice.lang.toLowerCase().startsWith("en"));
  return prefix ?? null;
}

function speakText(text: string, options: SpeakOptions): boolean {
  if (!isSpeechSupported() || !text.trim()) return false;
  const synth = window.speechSynthesis;
  // 切词前必须取消上一条，否则快速连播会叠音
  synth.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  const voice = pickVoice(options.accent, synth.getVoices());
  if (voice) utterance.voice = voice;
  utterance.lang = voice?.lang ?? options.accent;
  utterance.rate = options.rate;
  utterance.pitch = 1;
  synth.speak(utterance);
  return true;
}

/** 发音 Hook：单词发音 / 例句朗读 */
export function useSpeech() {
  const accent = useAppStore((state) => state.accent);
  const rate = useAppStore((state) => state.rate);
  const supported = useMemo(isSpeechSupported, []);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    if (!supported) return;
    const synth = window.speechSynthesis;
    const load = () => setVoices(synth.getVoices());
    load();
    // 部分浏览器音色列表异步就绪
    synth.addEventListener("voiceschanged", load);
    return () => {
      synth.removeEventListener("voiceschanged", load);
      synth.cancel();
    };
  }, [supported]);

  const speak = useCallback(
    (text: string) => speakText(text, { accent, rate }),
    [accent, rate]
  );

  const stop = useCallback(() => {
    if (supported) window.speechSynthesis.cancel();
  }, [supported]);

  return { speak, stop, supported, voices };
}
