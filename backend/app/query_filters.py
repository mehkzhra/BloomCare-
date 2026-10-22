"""Timezone-aware interval filters shared by patient and clinician record queries."""

from datetime import timezone

from fastapi import HTTPException


def time_range(query, column, start, end):
    for value in (start, end):
        if value is not None and value.tzinfo is None:
            raise HTTPException(422, "Date filters must include their timezone")
    if start and end and start >= end:
        raise HTTPException(422, "Choose a date range whose end follows its start")
    if start:
        query = query.where(column >= start.astimezone(timezone.utc))
    if end:
        query = query.where(column < end.astimezone(timezone.utc))
    return query
