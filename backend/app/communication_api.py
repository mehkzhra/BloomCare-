from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.appointment_service import (
    approved_doctor,
    participant_appointment,
    record_access_available,
    utc,
)
from app.database import get_db
from app.models import AccountEvent, CareMessage, MedicalReport, Notification, ReportShare, User
from app.notifications import notify
from app.schemas import Input
from app.security import current_user, require_role

router = APIRouter(prefix="/api")
patient = require_role("patient")
MAX_REPORT = 5 * 1024 * 1024


class ShareInput(Input):
    report_id: UUID
    consent: bool = Field(strict=True)


class MessageInput(Input):
    body: str = Field(min_length=1, max_length=4000)
    client_message_id: UUID


def report_out(r):
    return {
        "id": r.id,
        "title": r.title,
        "media_type": r.media_type,
        "byte_size": r.byte_size,
        "created_at": utc(r.created_at),
    }


def own_report(db, report_id, patient_id):
    row = db.scalar(
        select(MedicalReport).where(
            MedicalReport.id == report_id, MedicalReport.patient_id == patient_id
        )
    )
    if not row:
        raise HTTPException(404, "Report not found")
    return row


def downloadable(row):
    extension = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[row.media_type]
    return Response(
        row.content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="BloomCare-report-{row.id}.{extension}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/patients/me/reports", status_code=201)
async def upload_report(
    request: Request,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
    x_report_title: str = Header(default="Medical%20report"),
):
    title = unquote(x_report_title).strip()
    if not 2 <= len(title) <= 120 or any(ord(c) < 32 for c in title):
        raise HTTPException(422, "Use a report title of 2–120 characters")
    media_type = request.headers.get("content-type", "").split(";")[0]
    if media_type not in {"application/pdf", "image/png", "image/jpeg"}:
        raise HTTPException(415, "Upload a PDF, PNG or JPEG file")
    # Serialize a patient's uploads, preventing concurrent quota bypass.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    used = db.scalar(
        select(func.coalesce(func.sum(MedicalReport.byte_size), 0)).where(
            MedicalReport.patient_id == user.id
        )
    )
    count = db.scalar(
        select(func.count()).select_from(MedicalReport).where(MedicalReport.patient_id == user.id)
    )
    if count >= 100:
        raise HTTPException(413, "Maximum 100 reports per patient")
    content = bytearray()
    async for chunk in request.stream():
        if (
            len(content) + len(chunk) > MAX_REPORT
            or used + len(content) + len(chunk) > 50 * 1024 * 1024
        ):
            raise HTTPException(413, "Maximum 5 MB per report and 50 MB total per patient")
        content.extend(chunk)
    data = bytes(content)
    valid = (
        (media_type == "application/pdf" and data.startswith(b"%PDF-"))
        or (media_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"))
        or (media_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff"))
    )
    if not valid:
        raise HTTPException(415, "File signature does not match the selected format")
    row = MedicalReport(
        patient_id=user.id, title=title, media_type=media_type, byte_size=len(data), content=data
    )
    db.add(row)
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="REPORT_UPLOADED"))
    db.commit()
    return report_out(row)


@router.get("/patients/me/reports")
def reports(
    user: User = Depends(patient),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0, le=100000),
):
    return [
        report_out(r)
        for r in db.scalars(
            select(MedicalReport)
            .where(MedicalReport.patient_id == user.id)
            .order_by(MedicalReport.created_at.desc(), MedicalReport.id)
            .offset(offset)
            .limit(50)
        )
    ]


@router.get("/patients/me/reports/{report_id}/download")
def download_report(report_id: str, user: User = Depends(patient), db: Session = Depends(get_db)):
    return downloadable(own_report(db, report_id, user.id))


@router.delete("/patients/me/reports/{report_id}", status_code=204)
def remove_report(report_id: str, user: User = Depends(patient), db: Session = Depends(get_db)):
    row = own_report(db, report_id, user.id)
    db.execute(delete(ReportShare).where(ReportShare.report_id == row.id))
    db.delete(row)
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="REPORT_DELETED"))
    db.commit()


def episode(db, appointment_id, user, *, active=False):
    if user.role not in {"patient", "doctor"}:
        raise HTTPException(403, "Patient or doctor account required")
    if user.role == "doctor" and not approved_doctor(db, user.id):
        raise HTTPException(403, "Approved doctor account required")
    row = participant_appointment(db, appointment_id, user, lock=active)
    if active and not record_access_available(db, row):
        raise HTTPException(403, "An accepted, unexpired appointment is required")
    return row


@router.post("/patients/me/appointments/{appointment_id}/reports", status_code=201)
def share_report(
    appointment_id: str,
    data: ShareInput,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    if not data.consent:
        raise HTTPException(422, "Explicit consent is required to share a report")
    appointment = episode(db, appointment_id, user, active=True)
    row = own_report(db, str(data.report_id), user.id)
    if db.get(ReportShare, (appointment.id, row.id)) is None:
        db.add(ReportShare(appointment_id=appointment.id, report_id=row.id))
        notify(db, appointment.doctor_id, "REPORT_SHARED", appointment.id)
        db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="REPORT_SHARED"))
        db.commit()
    return report_out(row)


@router.delete("/patients/me/appointments/{appointment_id}/reports/{report_id}", status_code=204)
def unshare_report(
    appointment_id: str,
    report_id: str,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    appointment = episode(db, appointment_id, user)
    own_report(db, report_id, user.id)
    db.execute(
        delete(ReportShare).where(
            ReportShare.appointment_id == appointment.id, ReportShare.report_id == report_id
        )
    )
    db.commit()


@router.get("/doctors/me/appointments/{appointment_id}/reports")
def shared_reports(
    appointment_id: str, user: User = Depends(require_role("doctor")), db: Session = Depends(get_db)
):
    appointment = episode(db, appointment_id, user, active=True)
    return [
        report_out(r)
        for r in db.scalars(
            select(MedicalReport)
            .join(ReportShare, ReportShare.report_id == MedicalReport.id)
            .where(
                ReportShare.appointment_id == appointment.id,
                MedicalReport.patient_id == appointment.patient_id,
            )
            .order_by(MedicalReport.created_at.desc())
        )
    ]


@router.get("/doctors/me/appointments/{appointment_id}/reports/{report_id}/download")
def download_shared(
    appointment_id: str,
    report_id: str,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
):
    appointment = episode(db, appointment_id, user, active=True)
    if not db.get(ReportShare, (appointment.id, report_id)):
        raise HTTPException(404, "Shared report not found")
    return downloadable(own_report(db, report_id, appointment.patient_id))


def message_out(db, row):
    return {
        "id": row.id,
        "sender_id": row.sender_id,
        "sender_name": db.get(User, row.sender_id).full_name,
        "body": row.body,
        "created_at": utc(row.created_at),
    }


@router.get("/appointments/{appointment_id}/messages")
def messages(
    appointment_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0, le=100000),
):
    appointment = episode(db, appointment_id, user)
    return {
        "can_send": record_access_available(db, appointment),
        "messages": [
            message_out(db, r)
            for r in db.scalars(
                select(CareMessage)
                .where(CareMessage.appointment_id == appointment.id)
                .order_by(CareMessage.created_at.desc(), CareMessage.id)
                .offset(offset)
                .limit(50)
            )
        ],
    }


@router.post("/appointments/{appointment_id}/messages", status_code=201)
def send_message(
    appointment_id: str,
    data: MessageInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    appointment = episode(db, appointment_id, user)
    existing = db.scalar(
        select(CareMessage).where(
            CareMessage.appointment_id == appointment.id,
            CareMessage.sender_id == user.id,
            CareMessage.client_message_id == str(data.client_message_id),
        )
    )
    if existing:
        if existing.body != data.body:
            raise HTTPException(409, "Retry identifier already belongs to a different message")
        return message_out(db, existing)
    appointment = episode(db, appointment_id, user, active=True)
    row = CareMessage(
        appointment_id=appointment.id,
        sender_id=user.id,
        body=data.body,
        client_message_id=str(data.client_message_id),
    )
    db.add(row)
    recipient = appointment.doctor_id if user.role == "patient" else appointment.patient_id
    notify(db, recipient, "NEW_MESSAGE", appointment.id)
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="MESSAGE_SENT"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(CareMessage).where(
                CareMessage.appointment_id == appointment.id,
                CareMessage.sender_id == user.id,
                CareMessage.client_message_id == str(data.client_message_id),
            )
        )
        if not existing or existing.body != data.body:
            raise HTTPException(409, "Message retry conflict") from None
        return message_out(db, existing)
    return message_out(db, row)


@router.get("/notifications")
def notifications(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0, le=100000),
):
    rows = db.scalars(
        select(Notification)
        .where(Notification.recipient_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id)
        .offset(offset)
        .limit(50)
    ).all()
    unread = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.recipient_id == user.id, Notification.read.is_(False))
    )

    # Fetch references once instead of issuing up to 50 queries on every poll.
    assessment_records = {}
    if user.role == "patient":
        from app.models import Assessment

        ids = {row.assessment_id for row in rows if row.assessment_id}
        if ids:
            assessment_records = dict(
                db.execute(
                    select(Assessment.id, Assessment.health_record_id).where(
                        Assessment.id.in_(ids),
                        Assessment.patient_id == user.id,
                        Assessment.removed_at.is_(None),
                    )
                ).all()
            )

    return {
        "unread_count": unread,
        "items": [
            {
                "id": r.id,
                "kind": r.kind,
                "appointment_id": r.appointment_id,
                "health_record_id": assessment_records.get(r.assessment_id),
                "read": r.read,
                "created_at": utc(r.created_at),
            }
            for r in rows
        ],
    }


@router.patch("/notifications/{notification_id}/read")
def read_notification(
    notification_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.recipient_id == user.id
        )
    )
    if not row:
        raise HTTPException(404, "Notification not found")
    row.read = True
    db.commit()
    return {"id": row.id, "read": True}


@router.get("/patients/me/appointments/{appointment_id}/reports")
def patient_shared_reports(
    appointment_id: str, user: User = Depends(patient), db: Session = Depends(get_db)
):
    appointment = episode(db, appointment_id, user)
    return [
        report_out(r)
        for r in db.scalars(
            select(MedicalReport)
            .join(ReportShare, ReportShare.report_id == MedicalReport.id)
            .where(
                ReportShare.appointment_id == appointment.id, MedicalReport.patient_id == user.id
            )
        )
    ]
