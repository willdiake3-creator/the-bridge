"""
ORM layer over the tables defined in schema.sql.

schema.sql remains the source of truth for the actual DDL (including the
native Postgres enum types). These models intentionally store the same
enum-like values as plain strings rather than binding to SQLAlchemy's
native Enum type, so this file never tries to re-create a Postgres type
that schema.sql already owns. Valid values are enforced at the API layer
via the Pydantic schemas in schemas.py:

  degree_level: undergraduate | transfer | graduate | master | phd
  fee_status:   zero_fee | fee_waiver_available | fee_required
  app_status:   matched | sop_tailoring | staged_awaiting_user | submitted
                | action_required | decision_received | withdrawn
  req_type:     transcript | test_score | essay | recommendation_letter
                | passport | financial_proof | portfolio | interview | other
"""
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Column, String, Text, Integer, Numeric, Boolean, Date, DateTime,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


def uuid_pk():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class University(Base):
    __tablename__ = "universities"
    id = uuid_pk()
    name = Column(String, nullable=False)
    country = Column(String, nullable=False)
    region = Column(String, nullable=False)
    portal_system = Column(String)
    portal_url = Column(String)
    website = Column(String)
    logo_url = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    programs = relationship("Program", back_populates="university")


class FieldOfStudy(Base):
    __tablename__ = "fields_of_study"
    id = uuid_pk()
    slug = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)


class Program(Base):
    __tablename__ = "programs"
    id = uuid_pk()
    university_id = Column(UUID(as_uuid=True), ForeignKey("universities.id", ondelete="CASCADE"), nullable=False)
    field_of_study_id = Column(UUID(as_uuid=True), ForeignKey("fields_of_study.id"), nullable=False)
    name = Column(String, nullable=False)
    degree_level = Column(String, nullable=False)
    language = Column(String, default="English")
    duration_months = Column(Integer)
    application_deadline = Column(Date)
    intake_term = Column(String)
    fee_status = Column(String, nullable=False, default="fee_required")
    application_fee_cents = Column(Integer, default=0)
    currency = Column(String, default="USD")
    source_url = Column(String)
    last_verified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    university = relationship("University", back_populates="programs")
    field_of_study = relationship("FieldOfStudy")
    requirements = relationship("Requirement", back_populates="program", cascade="all, delete-orphan")
    fee_structure = relationship("FeeStructure", back_populates="program", uselist=False, cascade="all, delete-orphan")


class Scholarship(Base):
    __tablename__ = "scholarships"
    id = uuid_pk()
    name = Column(String, nullable=False)
    provider = Column(String)
    country = Column(String)
    covers = Column(String)
    eligibility_notes = Column(Text)
    application_url = Column(String)
    deadline = Column(Date)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class ProgramScholarship(Base):
    __tablename__ = "program_scholarships"
    program_id = Column(UUID(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"), primary_key=True)
    scholarship_id = Column(UUID(as_uuid=True), ForeignKey("scholarships.id", ondelete="CASCADE"), primary_key=True)


class Requirement(Base):
    __tablename__ = "requirements"
    id = uuid_pk()
    program_id = Column(UUID(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    is_mandatory = Column(Boolean, default=True)
    min_score = Column(Numeric)
    metadata_json = Column("metadata", JSONB, default=dict)

    program = relationship("Program", back_populates="requirements")


class FeeStructure(Base):
    __tablename__ = "fee_structures"
    id = uuid_pk()
    program_id = Column(UUID(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False)
    fee_status = Column(String, nullable=False)
    amount_cents = Column(Integer, default=0)
    currency = Column(String, default="USD")
    waiver_criteria = Column(JSONB, default=dict)
    waiver_requires_self_attestation = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    program = relationship("Program", back_populates="fee_structure")


class Student(Base):
    __tablename__ = "students"
    id = uuid_pk()
    email = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    password_hash = Column(String)  # null for Google-only accounts
    auth_provider = Column(String, default="password")  # 'google' | 'password'
    proxy_email = Column(String, unique=True)
    fee_strategy = Column(String, default="hybrid_smart_tiering")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    wallet = relationship("Wallet", back_populates="student", uselist=False)


class StudentDocument(Base):
    __tablename__ = "student_documents"
    id = uuid_pk()
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    doc_type = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    ocr_status = Column(String, default="pending")
    parsed_data = Column(JSONB, default=dict)
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class GpaConversion(Base):
    __tablename__ = "gpa_conversions"
    id = uuid_pk()
    student_document_id = Column(UUID(as_uuid=True), ForeignKey("student_documents.id", ondelete="CASCADE"), nullable=False)
    original_scale = Column(String, nullable=False)
    original_value = Column(Numeric, nullable=False)
    us_4_0 = Column(Numeric)
    ects_grade = Column(String)
    german_scale = Column(Numeric)
    uk_honours = Column(String)
    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Referee(Base):
    __tablename__ = "referees"
    id = uuid_pk()
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    relationship_label = Column("relationship", String)
    status = Column(String, default="not_sent")  # not_sent | sent | viewed | uploaded
    upload_link_token = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    reminder_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class RefereeDocument(Base):
    __tablename__ = "referee_documents"
    id = uuid_pk()
    referee_id = Column(UUID(as_uuid=True), ForeignKey("referees.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String, nullable=False)
    applies_to_program_ids = Column(ARRAY(UUID(as_uuid=True)), default=list)
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Essay(Base):
    __tablename__ = "essays"
    id = uuid_pk()
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    program_id = Column(UUID(as_uuid=True), ForeignKey("programs.id"))
    essay_type = Column(String, default="sop")
    draft_text = Column(Text)
    student_edited_text = Column(Text)
    status = Column(String, default="drafted")  # drafted | student_editing | approved
    originality_check_pct = Column(Numeric)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("student_id", "program_id", name="uq_student_program"),)
    id = uuid_pk()
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    program_id = Column(UUID(as_uuid=True), ForeignKey("programs.id"), nullable=False)
    status = Column(String, default="matched")
    essay_id = Column(UUID(as_uuid=True), ForeignKey("essays.id"))
    fee_charge_id = Column(UUID(as_uuid=True), ForeignKey("wallet_transactions.id"))
    staged_form_snapshot = Column(JSONB)
    submitted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    program = relationship("Program")


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    id = uuid_pk()
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False)
    detail = Column(JSONB, default=dict)
    occurred_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Wallet(Base):
    __tablename__ = "wallets"
    id = uuid_pk()
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), unique=True, nullable=False)
    balance_cents = Column(Integer, default=0)
    currency = Column(String, default="USD")
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("Student", back_populates="wallet")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    id = uuid_pk()
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"))
    type = Column(String, nullable=False)  # top_up | application_fee | waiver_no_charge | refund
    amount_cents = Column(Integer, nullable=False)
    kpay_reference = Column(String)  # Kpay payment intent / transaction id
    user_confirmed_at = Column(DateTime(timezone=True))  # null until the student taps confirm
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class InboxMessage(Base):
    __tablename__ = "inbox_messages"
    id = uuid_pk()
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"))
    from_address = Column(String, nullable=False)
    subject = Column(String)
    body_raw = Column(Text)
    category = Column(String)
    suggested_reply = Column(Text)
    student_sent_at = Column(DateTime(timezone=True))
    received_at = Column(DateTime(timezone=True), default=datetime.utcnow)
