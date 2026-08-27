import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db, get_current_student

router = APIRouter(tags=["referees"])


@router.post("/referees", response_model=schemas.RefereeOut, status_code=status.HTTP_201_CREATED)
def add_referee(
    payload: schemas.RefereeCreate,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    referee = models.Referee(
        student_id=current.id,
        name=payload.name,
        email=payload.email,
        relationship_label=payload.relationship_label,
        status="not_sent",
        upload_link_token=uuid.uuid4(),
    )
    db.add(referee)
    db.commit()
    db.refresh(referee)
    return referee


@router.get("/referees", response_model=list[schemas.RefereeOut])
def list_referees(
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    return db.query(models.Referee).filter_by(student_id=current.id).all()


@router.post("/referees/{referee_id}/send-link", response_model=schemas.RefereeOut)
def send_link(
    referee_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    referee = db.get(models.Referee, referee_id)
    if referee is None or referee.student_id != current.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referee not found")
    # In production: send an email via Postmark/SendGrid containing
    # f"{settings.frontend_url}/referee-portal.html?token={referee.upload_link_token}"
    referee.status = "sent"
    db.commit()
    db.refresh(referee)
    return referee


@router.post("/referees/{referee_id}/remind", response_model=schemas.RefereeOut)
def remind(
    referee_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    referee = db.get(models.Referee, referee_id)
    if referee is None or referee.student_id != current.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referee not found")
    referee.reminder_count += 1
    db.commit()
    db.refresh(referee)
    return referee


# ---- Public, token-authenticated — this is what the referee actually hits ----

@router.get("/referee-upload/{token}")
def referee_view(token: uuid.UUID, db: Session = Depends(get_db)):
    referee = db.query(models.Referee).filter_by(upload_link_token=token).first()
    if referee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This upload link isn't valid")
    if referee.status == "sent":
        referee.status = "viewed"
        db.commit()
    student = db.get(models.Student, referee.student_id)
    return {
        "referee_name": referee.name,
        "student_name": student.full_name if student else "",
        "relationship": referee.relationship_label,
    }


@router.post("/referee-upload/{token}")
def referee_submit(
    token: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    referee = db.query(models.Referee).filter_by(upload_link_token=token).first()
    if referee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This upload link isn't valid")

    # In production: stream `file` to encrypted object storage (S3/GCS) and
    # store the resulting URL below instead of a filename placeholder.
    doc = models.RefereeDocument(referee_id=referee.id, file_url=f"vault://referees/{referee.id}/{file.filename}")
    db.add(doc)
    referee.status = "uploaded"
    db.commit()
    return {"status": "received"}
