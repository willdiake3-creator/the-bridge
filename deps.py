import uuid
from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.security import decode_token
from app import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_student(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.Student:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_error
        student_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise credentials_error

    student = db.get(models.Student, student_id)
    if student is None:
        raise credentials_error
    return student
