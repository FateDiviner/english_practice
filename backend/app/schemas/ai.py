from pydantic import BaseModel


class AiPlaceholderOut(BaseModel):
    detail: str = "not implemented"
