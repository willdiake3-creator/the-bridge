import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db, get_current_student

router = APIRouter(prefix="/applications", tags=["applications"])


def _log_event(db: Session, application_id, event_type: str, detail: dict | None = None):
    db.add(models.ApplicationEvent(application_id=application_id, event_type=event_type, detail=detail or {}))


def _to_out(app_row: models.Application) -> schemas.ApplicationOut:
    program = app_row.program
    return schemas.ApplicationOut(
        id=app_row.id,
        program_id=app_row.program_id,
        status=app_row.status,
        submitted_at=app_row.submitted_at,
        created_at=app_row.created_at,
        program_name=program.name,
        university_name=program.university.name,
        fee_status=program.fee_status,
        application_fee_cents=program.application_fee_cents or 0,
        fee_confirmed=app_row.fee_charge_id is not None,
    )


@router.get("", response_model=list[schemas.ApplicationOut])
def list_applications(
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    rows = db.query(models.Application).filter_by(student_id=current.id).all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=schemas.ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: schemas.ApplicationCreate,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    program = db.get(models.Program, payload.program_id)
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Program not found")

    existing = db.query(models.Application).filter_by(
        student_id=current.id, program_id=payload.program_id
    ).first()
    if existing:
        return _to_out(existing)

    app_row = models.Application(student_id=current.id, program_id=payload.program_id, status="matched")
    db.add(app_row)
    db.flush()
    _log_event(db, app_row.id, "matched", {"program_name": program.name})
    db.commit()
    db.refresh(app_row)
    return _to_out(app_row)


@router.patch("/{application_id}/status", response_model=schemas.ApplicationOut)
def update_status(
    application_id: uuid.UUID,
    payload: schemas.ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    app_row = db.get(models.Application, application_id)
    if app_row is None or app_row.student_id != current.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    app_row.status = payload.status
    if payload.status == "submitted":
        from datetime import datetime
        app_row.submitted_at = datetime.utcnow()
    _log_event(db, app_row.id, "status_changed", {"to": payload.status})
    db.commit()
    db.refresh(app_row)
    return _to_out(app_row)


@router.get("/events/recent")
def recent_events(
    limit: int = 15,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    rows = (
        db.query(models.ApplicationEvent, models.Application, models.Program)
        .join(models.Application, models.ApplicationEvent.application_id == models.Application.id)
        .join(models.Program, models.Application.program_id == models.Program.id)
        .filter(models.Application.student_id == current.id)
        .order_by(models.ApplicationEvent.occurred_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "event_type": ev.event_type,
            "detail": ev.detail,
            "occurred_at": ev.occurred_at,
            "program_name": program.name,
            "application_id": app_row.id,
        }
        for ev, app_row, program in rows
    ]


@router.get("/{application_id}", response_model=schemas.ApplicationOut)
def get_application(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    app_row = db.get(models.Application, application_id)
    if app_row is None or app_row.student_id != current.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return _to_out(app_row)
