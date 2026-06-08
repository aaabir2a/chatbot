"""Org signup / login / me (JWT)."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Organization
from app.schemas import LoginRequest, OrgInfo, SignupRequest, TokenResponse
from app.services.auth import require_org
from app.services.security import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = body.email.lower()
    if db.query(Organization).filter(Organization.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered.")
    org = Organization(
        name=body.name, email=email, password_hash=hash_password(body.password)
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return TokenResponse(
        access_token=create_access_token(org.id), org=OrgInfo.model_validate(org)
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = body.email.lower()
    org = db.query(Organization).filter(Organization.email == email).first()
    if org is None or not org.password_hash or not verify_password(
        body.password, org.password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return TokenResponse(
        access_token=create_access_token(org.id), org=OrgInfo.model_validate(org)
    )


@router.get("/me", response_model=OrgInfo)
def me(org: Organization = Depends(require_org)) -> Organization:
    return org
