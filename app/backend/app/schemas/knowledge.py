from pydantic import BaseModel

class KBEntryCreate(BaseModel):
    content: str

class KBEntryOut(BaseModel):
    id: int
    content: str
    external_entry_id: str | None = None
    class Config:
        from_attributes = True