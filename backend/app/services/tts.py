"""调用 Windows 系统语音（SAPI）合成单词读音，并在本地缓存 WAV。"""

from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
import sys
import uuid
from pathlib import Path

from app.core.config import BACKEND_DIR

CACHE_DIR = BACKEND_DIR / "var" / "tts"
SYNTHESIS_TIMEOUT_SECONDS = 20
SPEECH_RATE = -1

# 优先使用指定口音的系统语音，未安装时回退到任意可用英语语音。
_ACCENT_VOICES = {
    "us": ("Microsoft Zira Desktop", "en-US"),
    "uk": ("Microsoft Hazel Desktop", "en-GB"),
}


class TtsUnavailableError(Exception):
    """系统语音不可用或合成失败。"""


def _digest(spelling: str, accent: str) -> str:
    voice, culture = _ACCENT_VOICES[accent]
    raw = f"{voice}|{culture}|{SPEECH_RATE}|{spelling}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _build_script(text_path: Path, output_path: Path, voice: str, culture: str) -> str:
    return f"""$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$text = [System.IO.File]::ReadAllText({_ps_quote(str(text_path))}, [System.Text.Encoding]::UTF8)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = @($synth.GetInstalledVoices() | Where-Object {{ $_.Enabled }})
$byName = $voices | Where-Object {{ $_.VoiceInfo.Name -eq {_ps_quote(voice)} }}
$picked = $byName | Select-Object -First 1
if (-not $picked) {{
  $byCulture = $voices | Where-Object {{ $_.VoiceInfo.Culture.Name -eq {_ps_quote(culture)} }}
  $picked = $byCulture | Select-Object -First 1
}}
if (-not $picked) {{
  $byLanguage = $voices | Where-Object {{ $_.VoiceInfo.Culture.Name -like 'en-*' }}
  $picked = $byLanguage | Select-Object -First 1
}}
if (-not $picked) {{ throw 'no English voice installed' }}
$synth.SelectVoice($picked.VoiceInfo.Name)
$synth.Rate = {SPEECH_RATE}
$synth.SetOutputToWaveFile({_ps_quote(str(output_path))})
try {{ $synth.Speak($text) }} finally {{ $synth.Dispose() }}
"""


def _run_powershell(script_path: Path) -> None:
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ],
            capture_output=True,
            timeout=SYNTHESIS_TIMEOUT_SECONDS,
            # 后台合成时不要弹出控制台窗口。
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TtsUnavailableError("系统语音调用失败") from exc

    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip() or "powershell 调用失败"
        raise TtsUnavailableError(detail[-300:])


async def synthesize_word_audio(spelling: str, accent: str = "us") -> Path:
    """合成单词读音并返回缓存文件；失败时抛出 TtsUnavailableError。"""
    if sys.platform != "win32":
        raise TtsUnavailableError("系统语音仅在 Windows 上可用")

    text = spelling.strip()
    if not text:
        raise TtsUnavailableError("没有可朗读的文本")

    accent_key = accent if accent in _ACCENT_VOICES else "us"
    voice, culture = _ACCENT_VOICES[accent_key]
    digest = _digest(text, accent_key)
    target = CACHE_DIR / f"{digest}.wav"
    if target.is_file() and target.stat().st_size > 0:
        return target

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    suffix = uuid.uuid4().hex
    text_path = CACHE_DIR / f"{digest}.txt"
    script_path = CACHE_DIR / f"{digest}-{suffix}.ps1"
    output_path = CACHE_DIR / f"{digest}-{suffix}.wav"
    text_path.write_text(text, encoding="utf-8")
    script_path.write_text(
        _build_script(text_path, output_path, voice, culture),
        encoding="utf-8-sig",
    )
    try:
        await asyncio.to_thread(_run_powershell, script_path)
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise TtsUnavailableError("系统语音没有生成音频")
        os.replace(output_path, target)
    finally:
        for path in (script_path, output_path, text_path):
            path.unlink(missing_ok=True)

    return target
