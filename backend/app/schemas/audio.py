from typing import Literal

from pydantic import BaseModel


class AudioOut(BaseModel):
    audio_url: str | None
    fallback: Literal["tts"] | None = None
