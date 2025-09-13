from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, BackgroundTasks, status
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password, create_refresh_jwt, gen_code, gen_slug
from app.core.redis import create_session, delete_session, delete_all_sessions
from app.core.rate_limit import set_cooldown, incr_failure, reset_failures, is_blocked, set_block, block_ttl
from app.db.session import get_db
from app.models.user import User
from app.models.verification import EmailVerification
from app.models.password_reset import PasswordReset
from app.schemas.auth import (
    RegisterIn,
    VerifyEmailIn,
    LoginIn,
    TokenPair,
    ForgotPasswordIn,
    ResetPasswordIn,
    ChangePasswordIn,
)
from app.schemas.user import UserOut
from app.schemas.common import Message
from app.services.email import send_email
from app.core.exceptions import raise_error
from app.core.error_codes import ErrorCode
from app.schemas.openapi import ERROR_RESPONSES

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Message, responses=ERROR_RESPONSES)
async def register(data: RegisterIn, db: AsyncSession = Depends(get_db), background: BackgroundTasks = None):
    # prevent duplicate accounts
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar():
        raise_error(ErrorCode.EMAIL_ALREADY_REGISTERED, status.HTTP_400_BAD_REQUEST, "Email already registered")

    # resend cooldown
    ok = await set_cooldown("verify:cooldown", data.email, settings.VERIFY_RESEND_COOLDOWN_SECONDS)
    if not ok:
        raise_error(
            ErrorCode.LOGIN_BLOCKED,
            status.HTTP_429_TOO_MANY_REQUESTS,
            user_message="Please wait before requesting another code",
        )

    code = gen_code(6)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.VERIFY_CODE_TTL_MINUTES)
    hashed = hash_password(data.password)

    # upsert email_verifications
    existing_ver = await db.execute(select(EmailVerification).where(EmailVerification.email == data.email))
    ver = existing_ver.scalar()
    if ver:
        await db.execute(
            update(EmailVerification)
            .where(EmailVerification.id == ver.id)
            .values(
                name=data.name,
                surname=data.surname,
                phone=data.phone,
                telegram=data.telegram,
                password_hash=hashed,
                code=code,
                expires_at=expires_at,
                created_at=datetime.now(timezone.utc),
            )
        )
    else:
        ver = EmailVerification(
            email=data.email,
            name=data.name,
            surname=data.surname,
            phone=data.phone,
            telegram=data.telegram,
            password_hash=hashed,
            code=code,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
        )
        db.add(ver)
    await db.commit()

    background.add_task(
        send_email,
        to_email=data.email,
        subject="Your confirmation code",
        body=f"Your code is: {code}. It expires in {settings.VERIFY_CODE_TTL_MINUTES} minutes.",
    )
    return {"message": "Verification code sent"}


@router.post("/verify-email", response_model=TokenPair, responses=ERROR_RESPONSES)
async def verify_email(data: VerifyEmailIn, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(EmailVerification).where(EmailVerification.email == data.email))
    ver = res.scalar()
    if not ver or ver.code != data.code:
        raise_error(ErrorCode.VERIFICATION_CODE_INVALID, status.HTTP_400_BAD_REQUEST, "Invalid code")
    if ver.expires_at <= datetime.now(timezone.utc):
        raise_error(ErrorCode.VERIFICATION_CODE_EXPIRED, status.HTTP_400_BAD_REQUEST, "Code expired")

    # create user
    user = User(
        name=ver.name,
        surname=ver.surname,
        email=ver.email,
        phone=ver.phone,
        telegram=ver.telegram,
        password_hash=ver.password_hash,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # delete verification row
    await db.execute(delete(EmailVerification).where(EmailVerification.id == ver.id))
    await db.commit()

    # auto-login
    session_token = await create_session(user.id)
    refresh_token = create_refresh_jwt(user.id, session_token)
    return TokenPair(session_token=session_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenPair, responses=ERROR_RESPONSES)
async def login(data: LoginIn, db: AsyncSession = Depends(get_db)):
    # Check block
    if await is_blocked(data.email):
        ttl = await block_ttl(data.email)
        raise_error(
            ErrorCode.LOGIN_BLOCKED,
            status.HTTP_429_TOO_MANY_REQUESTS,
            user_message="Too many attempts. Try later.",
            details={"retry_after_seconds": ttl},
        )

    res = await db.execute(select(User).where(User.email == data.email))
    user = res.scalar()

    if not user or not verify_password(data.password, user.password_hash):
        # Count a failure and maybe block
        count = await incr_failure(data.email, settings.LOGIN_ATTEMPT_WINDOW_SECONDS)
        if count >= settings.LOGIN_MAX_ATTEMPTS:
            await set_block(data.email, settings.LOGIN_BLOCK_SECONDS)
        raise_error(ErrorCode.INVALID_CREDENTIALS, status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    # Success → reset failure counter
    await reset_failures(data.email)

    session_token = await create_session(user.id)
    refresh_token = create_refresh_jwt(user.id, session_token)
    return TokenPair(session_token=session_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenPair, responses=ERROR_RESPONSES)
async def refresh(
    db: AsyncSession = Depends(get_db),
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
    x_refresh_token: str | None = Header(default=None, alias="X-Refresh-Token"),
):
    # We accept expired/invalid refresh JWT here as long as the session is valid
    if not x_session_token:
        raise_error(ErrorCode.TOKEN_MISSING, status.HTTP_401_UNAUTHORIZED, "Missing session token")

    # validate session maps to a real user
    from app.core.redis import get_session_user_id, extend_session

    uid = await get_session_user_id(x_session_token)
    if not uid:
        raise_error(ErrorCode.SESSION_INVALID, status.HTTP_401_UNAUTHORIZED, "Invalid session")
    user = await db.get(User, uid)
    if not user:
        raise_error(ErrorCode.USER_NOT_FOUND, status.HTTP_401_UNAUTHORIZED, "User not found")

    await extend_session(x_session_token)
    new_refresh = create_refresh_jwt(user.id, x_session_token)
    return TokenPair(session_token=x_session_token, refresh_token=new_refresh)


@router.post("/logout", response_model=Message, responses=ERROR_RESPONSES)
async def logout(
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
):
    if not x_session_token:
        raise_error(ErrorCode.TOKEN_MISSING, status.HTTP_401_UNAUTHORIZED, "Missing session token")
    await delete_session(x_session_token)
    return {"message": "Logged out"}


@router.post("/forgot-password", response_model=Message, responses=ERROR_RESPONSES)
async def forgot_password(data: ForgotPasswordIn, db: AsyncSession = Depends(get_db), background: BackgroundTasks = None):
    res = await db.execute(select(User).where(User.email == data.email))
    user = res.scalar()
    if not user:
        # do not reveal existence
        return {"message": "If the email exists, a reset link has been sent"}

    token = gen_slug(24)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES)

    pr = PasswordReset(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
        used=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(pr)
    await db.commit()

    reset_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/reset-password?token={token}"
    background.add_task(
        send_email,
        to_email=user.email,
        subject="Password reset",
        body=f"Use this link to reset your password (valid {settings.PASSWORD_RESET_TTL_MINUTES} minutes): {reset_url}",
    )
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password", response_model=Message, responses=ERROR_RESPONSES)
async def reset_password(data: ResetPasswordIn, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(PasswordReset).where(PasswordReset.token == data.token))
    pr = res.scalar()
    if not pr:
        raise_error(ErrorCode.PASSWORD_RESET_INVALID, status.HTTP_400_BAD_REQUEST, "Invalid token")
    if pr.used:
        raise_error(ErrorCode.PASSWORD_RESET_USED, status.HTTP_400_BAD_REQUEST, "Token already used")
    if pr.expires_at <= datetime.now(timezone.utc):
        raise_error(ErrorCode.PASSWORD_RESET_EXPIRED, status.HTTP_400_BAD_REQUEST, "Token expired")

    user = await db.get(User, pr.user_id)
    if not user:
        raise_error(ErrorCode.USER_NOT_FOUND, status.HTTP_404_NOT_FOUND, "User not found")

    user.password_hash = hash_password(data.new_password)
    pr.used = True
    await db.commit()

    # Invalidate all sessions for safety
    await delete_all_sessions(user.id)
    return {"message": "Password updated"}


@router.post("/change-password", response_model=TokenPair, responses=ERROR_RESPONSES)
async def change_password(
    payload: ChangePasswordIn,
    db: AsyncSession = Depends(get_db),
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
    current_user: User = Depends(lambda db=Depends(get_db), x_sess=Header(None, alias="X-Session-Token"): None),  # placeholder to keep order
):
    # Fetch user from session token
    from app.core.redis import get_session_user_id, delete_all_sessions

    if not x_session_token:
        raise_error(ErrorCode.TOKEN_MISSING, status.HTTP_401_UNAUTHORIZED, "Missing session token")

    uid = await get_session_user_id(x_session_token)
    if not uid:
        raise_error(ErrorCode.SESSION_INVALID, status.HTTP_401_UNAUTHORIZED, "Invalid session")
    user = await db.get(User, uid)
    if not user:
        raise_error(ErrorCode.USER_NOT_FOUND, status.HTTP_401_UNAUTHORIZED, "User not found")

    # Verify current password
    if not verify_password(payload.current_password, user.password_hash):
        raise_error(ErrorCode.INVALID_CREDENTIALS, status.HTTP_400_BAD_REQUEST, "Current password is incorrect")

    # Set new password
    user.password_hash = hash_password(payload.new_password)
    await db.commit()

    # Invalidate all sessions (including the one provided)
    await delete_all_sessions(user.id)

    # Create a new session + refresh JWT and return them (body only)
    new_session = await create_session(user.id)
    new_refresh = create_refresh_jwt(user.id, new_session)
    return TokenPair(session_token=new_session, refresh_token=new_refresh)
