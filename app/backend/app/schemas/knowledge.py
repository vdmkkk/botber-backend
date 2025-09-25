from pydantic import BaseModel
from app.models.enums import KBDataType, KBLangHint, KBEntryStatus

class KBEntryCreate(BaseModel):
    content: str
    data_type: KBDataType | None = None
    lang_hint: KBLangHint | None = None

class KBEntryOut(BaseModel):
    id: int
    content: str
    data_type: KBDataType
    lang_hint: KBLangHint
    status: KBEntryStatus
    external_entry_id: str | None = None
    execution_id: str | None = None
    class Config:
        from_attributes = True

class KnowledgeBaseOut(BaseModel):
    id: int
    entries: list[KBEntryOut] = []
    class Config:
        from_attributes = True