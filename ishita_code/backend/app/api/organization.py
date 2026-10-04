from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.organization import Organization, Team, TeamMembership
from app.models.user import User
from app.models.transformation import Transformation
from app.schemas.organization import OrganizationResponse, TeamResponse, TeamCreate, TeamUpdate, TeamMembershipChange
from app.schemas.user import UserResponse, UserUpdate
from app.api.deps import get_current_user, require_admin

router = APIRouter(tags=["organization"])


def _get_team(db: Session, team_id: str, org_id: str) -> Team:
    team = db.query(Team).filter(Team.id == team_id, Team.org_id == org_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


def _team_response(db: Session, team: Team) -> TeamResponse:
    return TeamResponse(
        id=team.id,
        org_id=team.org_id,
        name=team.name,
        description=team.description or "",
        member_ids=[membership.user_id for membership in team.memberships],
        active_work=db.query(Transformation).filter(Transformation.team_id == team.id, Transformation.status.in_(["draft", "processing", "changes_requested"])).count(),
        pending_reviews=db.query(Transformation).filter(Transformation.team_id == team.id, Transformation.status == "awaiting_review").count(),
        created_at=team.created_at,
    )

@router.get("/organization", response_model=OrganizationResponse)
def get_organization(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org = db.query(Organization).filter(Organization.id == current_user.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationResponse.model_validate(org)

@router.get("/teams", response_model=List[TeamResponse])
def list_teams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    teams = db.query(Team).filter(Team.org_id == current_user.org_id).all()
    res = []
    for t in teams:
        member_ids = [m.user_id for m in t.memberships]
        active_work = db.query(Transformation).filter(
            Transformation.team_id == t.id,
            Transformation.status.in_(["draft", "processing", "changes_requested"])
        ).count()
        pending_reviews = db.query(Transformation).filter(
            Transformation.team_id == t.id,
            Transformation.status == "awaiting_review"
        ).count()
        res.append(_team_response(db, t))
    return res

@router.post("/teams", response_model=TeamResponse)
def create_team(
    payload: TeamCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    team = Team(
        org_id=current_user.org_id,
        name=payload.name,
        description=payload.description or ""
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return _team_response(db, team)


@router.patch("/teams/{team_id}", response_model=TeamResponse)
def update_team(team_id: str, payload: TeamUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    team = _get_team(db, team_id, current_user.org_id)
    if payload.name is not None:
        team.name = payload.name.strip()
    if payload.description is not None:
        team.description = payload.description.strip()
    db.commit()
    db.refresh(team)
    return _team_response(db, team)


@router.post("/teams/{team_id}/members", response_model=TeamResponse)
def add_team_member(team_id: str, payload: TeamMembershipChange, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    team = _get_team(db, team_id, current_user.org_id)
    user = db.query(User).filter(User.id == payload.user_id, User.org_id == current_user.org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not db.query(TeamMembership).filter(TeamMembership.team_id == team.id, TeamMembership.user_id == user.id).first():
        db.add(TeamMembership(team_id=team.id, user_id=user.id))
        db.commit()
    return _team_response(db, team)


@router.delete("/teams/{team_id}/members/{user_id}", response_model=TeamResponse)
def remove_team_member(team_id: str, user_id: str, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    team = _get_team(db, team_id, current_user.org_id)
    membership = db.query(TeamMembership).filter(TeamMembership.team_id == team.id, TeamMembership.user_id == user_id).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Team membership not found")
    db.delete(membership)
    db.commit()
    return _team_response(db, team)


@router.delete("/teams/{team_id}", status_code=204)
def delete_team(team_id: str, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    team = _get_team(db, team_id, current_user.org_id)
    if db.query(Transformation).filter(Transformation.team_id == team.id).count():
        raise HTTPException(status_code=409, detail="Team has transformation history and cannot be deleted. Reassign active work first.")
    db.delete(team)
    db.commit()

@router.get("/users", response_model=List[UserResponse])
def list_users(
    team_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(User).filter(User.org_id == current_user.org_id)
    if team_id:
        user_ids = [m.user_id for m in db.query(TeamMembership).filter(TeamMembership.team_id == team_id).all()]
        query = query.filter(User.id.in_(user_ids))
    users = query.all()
    
    # Enrich with first team membership if exists
    results = []
    for u in users:
        ur = UserResponse.model_validate(u)
        first_membership = db.query(TeamMembership).filter(TeamMembership.user_id == u.id).first()
        if first_membership:
            ur.team_id = first_membership.team_id
        results.append(ur)
    return results

@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id, User.org_id == current_user.org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if payload.name is not None:
        user.name = payload.name
    if payload.role is not None:
        user.role = payload.role
    if payload.title is not None:
        user.title = payload.title
    if payload.status is not None:
        user.status = payload.status
    if payload.team_id is not None:
        if payload.team_id:
            _get_team(db, payload.team_id, current_user.org_id)
        # Update team membership
        db.query(TeamMembership).filter(TeamMembership.user_id == user.id).delete()
        if payload.team_id:
            db.add(TeamMembership(team_id=payload.team_id, user_id=user.id))

    db.commit()
    db.refresh(user)
    ur = UserResponse.model_validate(user)
    first_membership = db.query(TeamMembership).filter(TeamMembership.user_id == user.id).first()
    if first_membership:
        ur.team_id = first_membership.team_id
    return ur
