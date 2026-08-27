import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.deps import get_db, get_current_student
from app.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(student: models.Student, remember_me: bool) -> schemas.TokenResponse:
    sid = str(student.id)
    return schemas.TokenResponse(
        access_token=create_access_token(sid),
        refresh_token=create_refresh_token(sid, remember_me=remember_me),
    )


def _ensure_wallet(db: Session, student: models.Student) -> None:
    if student.wallet is None:
        db.add(models.Wallet(student_id=student.id, balance_cents=0, currency="USD"))
        db.commit()


@router.post("/register", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    if db.query(models.Student).filter_by(email=payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    student = models.Student(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        auth_provider="password",
        proxy_email=f"app_{uuid.uuid4().hex[:10]}@applybridge.com",
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    _ensure_wallet(db, student)
    return _issue_tokens(student, remember_me=False)


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter_by(email=payload.email).first()
    if not student or not student.password_hash or not verify_password(payload.password, student.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return _issue_tokens(student, remember_me=payload.remember_me)


@router.post("/google", response_model=schemas.TokenResponse)
def google_auth(payload: schemas.GoogleAuthRequest, db: Session = Depends(get_db)):
    try:
        claims = google_id_token.verify_oauth2_token(
            payload.id_token, google_requests.Request(), settings.google_client_id,
        )
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Google token")

    email = claims["email"]
    student = db.query(models.Student).filter_by(email=email).first()
    if student is None:
        student = models.Student(
            email=email,
            full_name=claims.get("name", email.split("@")[0]),
            auth_provider="google",
            proxy_email=f"app_{uuid.uuid4().hex[:10]}@applybridge.com",
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        _ensure_wallet(db, student)

    return _issue_tokens(student, remember_me=payload.remember_me)


@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh(refresh_token: str, db: Session = Depends(get_db)):
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError
        student_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    student = db.get(models.Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return _issue_tokens(student, remember_me=False)


@router.get("/me", response_model=schemas.StudentOut)
def me(current: models.Student = Depends(get_current_student)):
    return current


@router.patch("/me", response_model=schemas.StudentOut)
def update_me(
    payload: schemas.StudentUpdate,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    if payload.fee_strategy is not None:
        current.fee_strategy = payload.fee_strategy
    if payload.full_name is not None:
        current.full_name = payload.full_name
    db.commit()
    db.refresh(current)
    return current
