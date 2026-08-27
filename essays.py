import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db, get_current_student

router = APIRouter(prefix="/essays", tags=["essays"])


def _draft_sop(program_name: str, why_program: str, background: str, goals: str) -> str:
    """
    Placeholder for the Content & SOP Tailoring Agent. In production this
    calls out to an LLM with the student's intake answers plus the target
    program's focus areas (RAG'd from the programs/requirements tables).
    Swap this function for the real call — everything downstream (the
    student-edit loop, the originality check field, approval gating)
    stays the same.
    """
    return (
        f"When I trace back what pulled me toward {program_name}, it comes down to one thing: "
        f"{why_program[0].lower()}{why_program[1:]}\n\n"
        f"That interest didn't come from nowhere. {background} Each of those experiences pushed me "
        "toward the same conclusion — that I understand these systems well enough to be dangerous "
        "with them, but not yet well enough to be rigorous. I'm applying here specifically because "
        "that gap is exactly what this program is built to close.\n\n"
        f"I don't think of this degree as a credential to collect. {goals} What I'm looking for is "
        "the grounding and the environment to get there — and this program is where I want to do it."
    )


@router.post("/draft", response_model=schemas.EssayOut, status_code=status.HTTP_201_CREATED)
def draft_essay(
    payload: schemas.EssayDraftRequest,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    program = db.get(models.Program, payload.program_id)
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Program not found")

    draft_text = _draft_sop(program.name, payload.why_program, payload.background, payload.goals)
    essay = models.Essay(
        student_id=current.id,
        program_id=payload.program_id,
        essay_type=payload.essay_type,
        draft_text=draft_text,
        student_edited_text=draft_text,
        status="drafted",
        originality_check_pct=100,  # placeholder for the real plagiarism-check integration
    )
    db.add(essay)
    db.commit()
    db.refresh(essay)
    return essay


@router.patch("/{essay_id}", response_model=schemas.EssayOut)
def edit_essay(
    essay_id: uuid.UUID,
    payload: schemas.EssayEditRequest,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    essay = db.get(models.Essay, essay_id)
    if essay is None or essay.student_id != current.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Essay not found")
    essay.student_edited_text = payload.student_edited_text
    essay.status = "student_editing"
    db.commit()
    db.refresh(essay)
    return essay


@router.post("/{essay_id}/approve", response_model=schemas.EssayOut)
def approve_essay(
    essay_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    essay = db.get(models.Essay, essay_id)
    if essay is None or essay.student_id != current.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Essay not found")
    essay.status = "approved"
    db.commit()
    db.refresh(essay)
    return essay
