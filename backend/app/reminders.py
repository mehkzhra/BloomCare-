from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.appointment_service import utc
from app.database import SessionLocal
from app.models import MedicationEntry, MedicationReminder, Notification, User, utc_now


def process_reminders(now=None):
    now = now or utc_now()
    with SessionLocal() as db:
        rows = db.scalars(
            select(MedicationReminder)
            .join(MedicationEntry, MedicationEntry.id == MedicationReminder.medication_id)
            .join(User, User.id == MedicationReminder.patient_id)
            .where(
                MedicationReminder.cancelled.is_(False),
                MedicationReminder.due_at <= now,
                MedicationEntry.active.is_(True),
                User.active.is_(True),
            )
            .with_for_update(skip_locked=True)
            .limit(100)
        ).all()
        for row in rows:
            due = utc(row.due_at)
            key = str(uuid5(NAMESPACE_URL, f"bloomcare-reminder:{row.id}:{due.isoformat()}"))
            if db.get(Notification, key) is None:
                db.add(
                    Notification(id=key, recipient_id=row.patient_id, kind="MEDICATION_REMINDER")
                )
            row.last_fired_at = now
            if row.period_hours:
                period = timedelta(hours=row.period_hours)
                row.due_at = due + period * (int((now - due) / period) + 1)
            else:
                row.cancelled = True
        try:
            db.commit()
        except IntegrityError:
            # A competing worker inserted the same deterministic notification.
            db.rollback()
