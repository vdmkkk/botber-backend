from pydantic import BaseModel

class BotCreate(BaseModel):
    title: str
    description: str
    content: dict = {}
    activation_code: str
    rate: int

class BotUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    content: dict | None = None
    activation_code: str | None = None
    rate: int | None = None

class BotOut(BaseModel):
    id: int
    title: str
    description: str
    content: dict
    activation_code: str
    rate: int

    class Config:
        from_attributes = True
