import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db, get_current_student
from app.payments.base import PaymentProvider
from app.payments.kpay import get_payment_provider

router = APIRouter(prefix="/wallet", tags=["wallet"])


def _get_or_create_wallet(db: Session, student: models.Student) -> models.Wallet:
    if student.wallet is None:
        wallet = models.Wallet(student_id=student.id, balance_cents=0, currency="USD")
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
        return wallet
    return student.wallet


@router.get("", response_model=schemas.WalletOut)
def get_wallet(
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    return _get_or_create_wallet(db, current)


@router.get("/transactions", response_model=list[schemas.WalletTransactionOut])
def list_transactions(
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    wallet = _get_or_create_wallet(db, current)
    return (
        db.query(models.WalletTransaction)
        .filter_by(wallet_id=wallet.id)
        .order_by(models.WalletTransaction.created_at.desc())
        .all()
    )


@router.post("/topup", response_model=schemas.TopUpResponse)
def top_up(
    payload: schemas.TopUpRequest,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
    provider: PaymentProvider = Depends(get_payment_provider),
):
    """
    Starts a Kpay checkout session for the requested amount. The wallet
    balance is only credited once the /wallet/kpay-webhook handler below
    confirms the payment actually succeeded — never on this call alone.
    """
    wallet = _get_or_create_wallet(db, current)
    session = provider.create_checkout(
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        student_id=str(current.id),
        purpose="wallet_topup",
        metadata={"wallet_id": str(wallet.id)},
    )
    db.add(models.WalletTransaction(
        wallet_id=wallet.id,
        type="top_up",
        amount_cents=payload.amount_cents,
        kpay_reference=session.reference,
        user_confirmed_at=None,  # flips to non-null once the webhook confirms success
    ))
    db.commit()
    return schemas.TopUpResponse(
        checkout_url=session.checkout_url,
        kpay_reference=session.reference,
        amount_cents=payload.amount_cents,
    )


@router.post("/kpay-webhook", include_in_schema=False)
async def kpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
):
    body = await request.body()
    signature = request.headers.get("X-Kpay-Signature", "")
    try:
        event = provider.parse_webhook(payload=body, signature_header=signature)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature")

    tx = db.query(models.WalletTransaction).filter_by(kpay_reference=event.reference).first()
    if tx is None:
        # Unknown reference — ack anyway so Kpay doesn't retry forever, but don't touch a balance.
        return {"received": True}

    if event.status == "succeeded" and tx.user_confirmed_at is None:
        from datetime import datetime
        tx.user_confirmed_at = datetime.utcnow()
        wallet = db.get(models.Wallet, tx.wallet_id)
        if tx.type == "top_up":
            wallet.balance_cents += tx.amount_cents
        db.commit()

    return {"received": True}


@router.post("/fee/confirm", response_model=schemas.WalletTransactionOut)
def confirm_application_fee(
    payload: schemas.FeeConfirmRequest,
    db: Session = Depends(get_db),
    current: models.Student = Depends(get_current_student),
):
    """
    The one-tap confirmation the student gives on the staged-submission
    screen before a fee-required application's charge actually fires.
    Debits the pre-funded wallet balance directly — no card issuance
    needed since the platform already holds the funds from a prior top-up.
    """
    app_row = db.get(models.Application, payload.application_id)
    if app_row is None or app_row.student_id != current.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if not payload.confirmed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Confirmation required to charge a fee")

    program = db.get(models.Program, app_row.program_id)
    fee_cents = program.application_fee_cents or 0
    wallet = _get_or_create_wallet(db, current)

    if program.fee_status == "zero_fee" or fee_cents == 0:
        tx_type, charge_amount = "waiver_no_charge", 0
    else:
        if wallet.balance_cents < fee_cents:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "Insufficient wallet balance — top up first")
        tx_type, charge_amount = "application_fee", fee_cents
        wallet.balance_cents -= fee_cents

    from datetime import datetime
    tx = models.WalletTransaction(
        wallet_id=wallet.id,
        application_id=app_row.id,
        type=tx_type,
        amount_cents=charge_amount,
        user_confirmed_at=datetime.utcnow(),
    )
    db.add(tx)
    db.flush()
    app_row.fee_charge_id = tx.id
    db.add(models.ApplicationEvent(application_id=app_row.id, event_type="fee_confirmed", detail={"amount_cents": charge_amount}))
    db.commit()
    db.refresh(tx)
    return tx
