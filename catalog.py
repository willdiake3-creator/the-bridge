from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db

router = APIRouter(tags=["catalog"])


@router.get("/fields")
def list_fields(db: Session = Depends(get_db)):
    rows = db.query(models.FieldOfStudy).order_by(models.FieldOfStudy.category, models.FieldOfStudy.name).all()
    return [{"id": r.id, "slug": r.slug, "category": r.category, "name": r.name} for r in rows]


@router.get("/programs", response_model=list[schemas.ProgramOut])
def search_programs(
    db: Session = Depends(get_db),
    field_slug: Optional[str] = None,
    degree_level: Optional[str] = None,
    region: Optional[str] = None,
    fee_status: Optional[str] = None,
    q: Optional[str] = Query(None, description="free-text search over program/university name"),
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    query = (
        db.query(models.Program)
        .join(models.University, models.Program.university_id == models.University.id)
        .join(models.FieldOfStudy, models.Program.field_of_study_id == models.FieldOfStudy.id)
    )
    if field_slug:
        query = query.filter(models.FieldOfStudy.slug == field_slug)
    if degree_level:
        query = query.filter(models.Program.degree_level == degree_level)
    if region:
        query = query.filter(models.University.region == region)
    if fee_status:
        query = query.filter(models.Program.fee_status == fee_status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Program.name.ilike(like)) | (models.University.name.ilike(like))
        )

    rows = query.offset(offset).limit(limit).all()
    return [
        schemas.ProgramOut(
            id=p.id,
            name=p.name,
            degree_level=p.degree_level,
            fee_status=p.fee_status,
            application_fee_cents=p.application_fee_cents or 0,
            currency=p.currency,
            application_deadline=p.application_deadline,
            university_name=p.university.name,
            country=p.university.country,
            region=p.university.region,
            field_slug=p.field_of_study.slug,
            field_name=p.field_of_study.name,
        )
        for p in rows
    ]


@router.get("/programs/{program_id}", response_model=schemas.ProgramDetailOut)
def get_program(program_id: uuid.UUID, db: Session = Depends(get_db)):
    p = db.get(models.Program, program_id)
    if p is None:
        raise HTTPException(404, "Program not found")
    return schemas.ProgramDetailOut(
        id=p.id, name=p.name, degree_level=p.degree_level, fee_status=p.fee_status,
        application_fee_cents=p.application_fee_cents or 0, currency=p.currency,
        application_deadline=p.application_deadline,
        university_name=p.university.name, country=p.university.country, region=p.university.region,
        field_slug=p.field_of_study.slug, field_name=p.field_of_study.name,
        requirements=[
            {"type": r.type, "description": r.description, "is_mandatory": r.is_mandatory}
            for r in p.requirements
        ],
    )


@router.get("/programs/{program_id}/scholarships", response_model=list[schemas.ScholarshipOut])
def program_scholarships(program_id: uuid.UUID, db: Session = Depends(get_db)):
    links = db.query(models.ProgramScholarship).filter_by(program_id=program_id).all()
    ids = [l.scholarship_id for l in links]
    if not ids:
        return []
    return db.query(models.Scholarship).filter(models.Scholarship.id.in_(ids)).all()
