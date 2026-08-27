import uuid
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app import models
from app.deps import get_db, get_current_student

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    valid_types = {"transcript", "test_score", "passport", "financial_proof", "portfolio", "other"}
    if doc_type not in valid_types:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"doc_type must be one of {sorted(valid_types)}")

    # In production: stream to encrypted object storage (S3/GCS) and store
    # the resulting URL. The Ingestion & Vault Agent (Vision-OCR) would then
    # pick this up async and populate parsed_data / ocr_status below.
    doc = models.StudentDocument(
        student_id=current.id,
        doc_type=doc_type,
        file_url=f"vault://{current.id}/{doc_type}/{file.filename}",
        ocr_status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "doc_type": doc.doc_type, "ocr_status": doc.ocr_status, "file_url": doc.file_url}


@router.get("")
def list_documents(
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    docs = db.query(models.StudentDocument).filter_by(student_id=current.id).all()
    return [
        {"id": d.id, "doc_type": d.doc_type, "ocr_status": d.ocr_status, "uploaded_at": d.uploaded_at}
        for d in docs
    ]


def _round2(x) -> float:
    return float(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@router.post("/{document_id}/convert-gpa")
def convert_gpa(
    document_id: uuid.UUID,
    original_value: float,
    original_scale: str = "100-point",
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    """
    Placeholder for the Ingestion Agent's real grade-conversion logic —
    same honesty pattern as the SOP draft stub: simple formulas here,
    swap for the real OCR + conversion-table pipeline later without
    touching the schema or the frontend that reads it.
    """
    doc = db.get(models.StudentDocument, document_id)
    if doc is None or doc.student_id != current.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    pct = original_value if original_scale == "100-point" else original_value
    us_4_0 = _round2(min(pct / 100 * 4.0, 4.0))
    german = _round2(max(1.0, min(5.0, 4.0 - (pct / 100 * 3.0))))
    ects = "A" if pct >= 90 else "B" if pct >= 80 else "C" if pct >= 70 else "D" if pct >= 60 else "E"
    uk = "1st" if pct >= 70 else "2:1" if pct >= 60 else "2:2" if pct >= 50 else "3rd"

    conv = models.GpaConversion(
        student_document_id=doc.id,
        original_scale=original_scale,
        original_value=original_value,
        us_4_0=us_4_0,
        ects_grade=ects,
        german_scale=german,
        uk_honours=uk,
    )
    doc.ocr_status = "parsed"
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {
        "original_scale": original_scale, "original_value": original_value,
        "us_4_0": us_4_0, "ects_grade": ects, "german_scale": german, "uk_honours": uk,
    }


@router.get("/gpa-conversions")
def list_gpa_conversions(
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    doc_ids = [d.id for d in db.query(models.StudentDocument).filter_by(student_id=current.id).all()]
    if not doc_ids:
        return []
    rows = db.query(models.GpaConversion).filter(models.GpaConversion.student_document_id.in_(doc_ids)).all()
    return [
        {
            "original_scale": r.original_scale, "original_value": float(r.original_value),
            "us_4_0": float(r.us_4_0) if r.us_4_0 is not None else None,
            "ects_grade": r.ects_grade,
            "german_scale": float(r.german_scale) if r.german_scale is not None else None,
            "uk_honours": r.uk_honours,
        }
        for r in rows
    ]
