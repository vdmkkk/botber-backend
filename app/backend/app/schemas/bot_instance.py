from pydantic import BaseModel
from app.models.enums import InstanceStatus
from app.schemas.knowledge import KnowledgeBaseOut

class InstanceCreate(BaseModel):
    bot_id: int
    title: str
    config: dict = {}

class InstanceUpdate(BaseModel):
    title: str | None = None
    config: dict | None = None
    status: InstanceStatus | None = None

class InstanceStatusUpdate(BaseModel):
    status: InstanceStatus

class InstanceOut(BaseModel):
    id: int
    user_id: int
    bot_id: int
    instance_id: str 
    title: str
    config: dict
    status: InstanceStatus

    class Config:
        from_attributes = True

class InstanceDetailOut(InstanceOut):
    kb: KnowledgeBaseOut | None = None