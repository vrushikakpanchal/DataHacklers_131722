from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.access import Invitation, hash_one_time_token
from app.models.audit import AuditEvent
from app.models.organization import Team, TeamMembership
from app.models.user import User
from app.schemas.access import InvitationAccept, InvitationCreate, InvitationResponse
from app.schemas.user import UserResponse
from app.services.mailer import send_transactional_email

router = APIRouter(prefix="/invitations", tags=["invitations"])


def _invite_url(token: str) -> str:
    return f"{settings.PUBLIC_APP_URL.rstrip('/')}/invite?token={token}"


def _response(invitation: Invitation, delivery_status: str, token: str | None = None) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id, email=invitation.email, role=invitation.role,
        team_id=invitation.team_id, status=invitation.status,
        expires_at=invitation.expires_at, delivery_status=delivery_status,
        invite_url=_invite_url(token) if token and delivery_status == "manual" else None,
    )


@router.post("", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(payload: InvitationCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="A valid email address is required")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    if payload.team_id and not db.query(Team).filter(Team.id == payload.team_id, Team.org_id == current_user.org_id).first():
        raise HTTPException(status_code=422, detail="Team must belong to your organization")
    db.query(Invitation).filter(Invitation.org_id == current_user.org_id, Invitation.email == email, Invitation.status == "pending").update({"status": "revoked"})
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        org_id=current_user.org_id, email=email, role=payload.role, team_id=payload.team_id,
        invited_by=current_user.id, token_hash=hash_one_time_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invitation)
    db.add(AuditEvent(actor_id=current_user.id, action="INVITATION_CREATED", target_type="invitation", target_id=invitation.id,
        team_id=payload.team_id, summary=f"{current_user.name} invited {email} as {payload.role}", details={"email": email, "role": payload.role}))
    db.commit()
    db.refresh(invitation)
    url = _invite_url(token)
    try:
        delivery = send_transactional_email(email, "SENTINEL invitation", f"Accept your SENTINEL invitation: {url}\nThis link expires in seven days.")
    except Exception:
        delivery = "manual"
    return _response(invitation, delivery, token)


@router.post("/accept", response_model=UserResponse)
def accept_invitation(payload: InvitationAccept, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    invitation = db.query(Invitation).filter(Invitation.token_hash == hash_one_time_token(payload.token)).first()
    if not invitation or invitation.status != "pending" or invitation.expires_at < now:
        raise HTTPException(status_code=400, detail="Invitation link is invalid, expired, or has already been used")
    if db.query(User).filter(User.email == invitation.email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    initials = "".join(part[:1].upper() for part in payload.name.split()[:2])
    user = User(org_id=invitation.org_id, email=invitation.email, name=payload.name.strip(), role=invitation.role,
        hashed_password=get_password_hash(payload.password), initials=initials, status="active")
    db.add(user)
    db.flush()
    if invitation.team_id:
        db.add(TeamMembership(team_id=invitation.team_id, user_id=user.id))
    invitation.status = "accepted"
    invitation.accepted_at = now
    db.add(AuditEvent(actor_id=user.id, action="INVITATION_ACCEPTED", target_type="invitation", target_id=invitation.id,
        team_id=invitation.team_id, summary=f"{user.name} accepted an invitation", details={"role": user.role}))
    db.commit()
    db.refresh(user)
    response = UserResponse.model_validate(user)
    response.team_id = invitation.team_id
    return response
