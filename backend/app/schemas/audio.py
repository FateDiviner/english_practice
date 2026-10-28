from typing import Literal

from pydantic import BaseModel


class AudioOut(BaseModel):
    audio_url: str | None
    tts_text: str | None = None
    fallback: Literal["tts"] | None = None
