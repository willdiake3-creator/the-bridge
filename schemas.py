import uuid
from datetime import datetime, date
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, Field, ConfigDict

DegreeLevel = Literal["undergraduate", "transfer", "graduate", "master", "phd"]
FeeStatus = Literal["zero_fee", "fee_waiver_available", "fee_required"]
AppStatus = Literal[
    "matched", "sop_tailoring", "staged_awaiting_user", "submitted",
    "action_required", "decision_received", "withdrawn",
]

# ---------------- Auth ----------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class GoogleAuthRequest(BaseModel):
    id_token: str
    remember_me: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str
    proxy_email: Optional[str]
    fee_strategy: str


class StudentUpdate(BaseModel):
    fee_strategy: Optional[Literal[
        "zero_fee_only", "fee_waiver_priority", "fee_based_prefunded", "hybrid_smart_tiering",
    ]] = None
    full_name: Optional[str] = None


# ---------------- Catalog ----------------

class ProgramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    degree_level: str
    fee_status: str
    application_fee_cents: int
    currency: str
    application_deadline: Optional[date]
    university_name: str
    country: str
    region: str
    field_slug: str
    field_name: str


class RequirementOut(BaseModel):
    type: str
    description: str
    is_mandatory: bool


class ProgramDetailOut(ProgramOut):
    requirements: list[RequirementOut] = []


class ScholarshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    provider: Optional[str]
    covers: Optional[str]
    eligibility_notes: Optional[str]


# ---------------- Applications ----------------

class ApplicationCreate(BaseModel):
    program_id: uuid.UUID


class ApplicationOut(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    status: AppStatus
    submitted_at: Optional[datetime]
    created_at: datetime
    program_name: str
    university_name: str
    fee_status: str
    application_fee_cents: int
    fee_confirmed: bool = False


class ApplicationStatusUpdate(BaseModel):
    status: AppStatus


# ---------------- Essays ----------------

class EssayDraftRequest(BaseModel):
    program_id: uuid.UUID
    essay_type: str = "sop"
    why_program: str
    background: str
    goals: str


class EssayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    program_id: Optional[uuid.UUID]
    essay_type: str
    draft_text: Optional[str]
    student_edited_text: Optional[str]
    status: str


class EssayEditRequest(BaseModel):
    student_edited_text: str


# ---------------- Referees ----------------

class RefereeCreate(BaseModel):
    name: str
    email: EmailStr
    relationship_label: Optional[str] = None


class RefereeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    email: EmailStr
    status: str
    upload_link_token: uuid.UUID


class RefereeUploadSubmit(BaseModel):
    applies_to_application_ids: list[uuid.UUID] = []


# ---------------- Wallet / Kpay ----------------

class TopUpRequest(BaseModel):
    amount_cents: int = Field(gt=0)
    currency: str = "USD"


class TopUpResponse(BaseModel):
    checkout_url: str
    kpay_reference: str
    amount_cents: int


class FeeConfirmRequest(BaseModel):
    application_id: uuid.UUID
    confirmed: bool = True


class WalletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    balance_cents: int
    currency: str


class WalletTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: str
    amount_cents: int
    kpay_reference: Optional[str]
    user_confirmed_at: Optional[datetime]
    created_at: datetime
