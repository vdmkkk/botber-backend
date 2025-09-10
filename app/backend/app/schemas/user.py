from pydantic import BaseModel, EmailStr, Field

class UserOut(BaseModel):
    id: int
    name: str
    surname: str
    email: EmailStr
    phone: str
    telegram: str | None = None
    balance: int

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: str | None = None
    surname: str | None = None
    phone: str | None = None
    telegram: str | None = None

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)