from datetime import datetime, timedelta, timezone
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.config import settings
from app.models.access import PasswordResetToken, hash_one_time_token
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserResponse
from app.schemas.access import PasswordResetConfirm, PasswordResetRequest, PasswordResetRequestResponse
from app.api.deps import get_current_user
from app.services.mailer import send_transactional_email

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or user.status != "active" or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Update last_active
    user.last_active = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/password-reset/request", response_model=PasswordResetRequestResponse)
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    """Issue a single-use reset token without revealing whether an email exists."""
    user = db.query(User).filter(User.email == payload.email.lower().strip(), User.status == "active").first()
    if not user:
        return PasswordResetRequestResponse(accepted=True, delivery_status="email")
    now = datetime.now(timezone.utc)
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).update({"used_at": now})
    token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(user_id=user.id, token_hash=hash_one_time_token(token), expires_at=now + timedelta(hours=1)))
    db.commit()
    url = f"{settings.PUBLIC_APP_URL.rstrip('/')}/reset-password?token={token}"
    try:
        delivery = send_transactional_email(user.email, "Reset your SENTINEL password", f"Reset your SENTINEL password: {url}\nThis link expires in one hour.")
    except Exception:
        delivery = "manual"
    return PasswordResetRequestResponse(
        accepted=True,
        delivery_status=delivery,
        reset_url=url if delivery == "manual" and settings.ENVIRONMENT != "production" else None,
    )


@router.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    reset = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == hash_one_time_token(payload.token)).first()
    if not reset or reset.used_at is not None or reset.expires_at < now:
        raise HTTPException(status_code=400, detail="Password reset link is invalid, expired, or has already been used")
    user = db.query(User).filter(User.id == reset.user_id, User.status == "active").first()
    if not user:
        raise HTTPException(status_code=400, detail="Password reset link is invalid")
    user.hashed_password = get_password_hash(payload.password)
    reset.used_at = now
    db.commit()
    return {"message": "Password updated successfully. Please sign in."}

@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    return {"message": "Logged out successfully."}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
