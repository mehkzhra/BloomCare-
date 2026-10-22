from app.models import Notification


def notify(db, recipient_id, kind, appointment_id=None, *, assessment_id=None):
    db.add(
        Notification(
            recipient_id=recipient_id,
            kind=kind,
            appointment_id=appointment_id,
            assessment_id=assessment_id,
        )
    )
