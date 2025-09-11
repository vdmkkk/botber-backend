from pydantic import BaseModel, Field, EmailStr

class RegisterIn(BaseModel):
    name: str
    surname: str
    email: EmailStr
    phone: str
    password: str = Field(min_length=6)
    telegram: str | None = None

class VerifyEmailIn(BaseModel):
    email: EmailStr
    code: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenPair(BaseModel):
    session_token: str
    refresh_token: str

class ForgotPasswordIn(BaseModel):
    email: EmailStr

class ResetPasswordIn(BaseModel):
    token: str
    new_password: str = Field(min_length=6)

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)