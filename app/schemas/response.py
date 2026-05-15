from pydantic import BaseModel


class BotResponse(BaseModel):
    text: str
    reply: bool = True
