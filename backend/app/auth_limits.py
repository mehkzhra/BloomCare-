"""Database-atomic, HMAC-keyed authentication limits shared by API processes."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address

from fastapi import HTTPException
from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import get_settings
from app.models import AuthRateBucket


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def consume(db, scope, identity, limit, seconds, *, now=None):
    now = now or datetime.now(timezone.utc)
    key = hmac.new(
        get_settings().jwt_secret.encode(), f"{scope}:{identity}".encode(), hashlib.sha256
    ).hexdigest()
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    expired = AuthRateBucket.window_start <= now - timedelta(seconds=seconds)
    statement = insert(AuthRateBucket).values(key=key, window_start=now, attempts=1)
    statement = statement.on_conflict_do_update(
        index_elements=[AuthRateBucket.key],
        set_={
            "window_start": case((expired, now), else_=AuthRateBucket.window_start),
            "attempts": case((expired, 1), else_=AuthRateBucket.attempts + 1),
        },
    ).returning(AuthRateBucket.attempts, AuthRateBucket.window_start)
    attempts, start = db.execute(statement).one()
    db.execute(delete(AuthRateBucket).where(AuthRateBucket.window_start < now - timedelta(days=2)))
    # Persist even rejected attempts; a failed login must not undo the counter.
    db.commit()
    if attempts > limit:
        retry = max(1, int((utc(start) + timedelta(seconds=seconds) - now).total_seconds()) + 1)
        raise HTTPException(
            429,
            "Too many attempts. Please wait before trying again.",
            headers={"Retry-After": str(retry)},
        )


def peer_identity(request):
    peer = request.client.host if request.client else "unknown-peer"
    if get_settings().auth_proxy_header == "render-cloudflare":
        # Enable only behind Render's public Cloudflare edge, which overwrites
        # this header. X-Forwarded-For may include caller-supplied entries.
        try:
            return str(ip_address(request.headers.get("cf-connecting-ip", "")))
        except ValueError:
            pass
    return peer


def enforce(db, request, scope, email=None):
    peer = peer_identity(request)
    limits = {
        "login": (50, 10, 900),
        "register": (10, None, 3600),
        "recovery": (20, 3, 3600),
        "confirm": (30, None, 900),
    }
    ip_limit, account_limit, seconds = limits[scope]
    consume(db, scope + ":peer", peer, ip_limit, seconds)
    if email is not None and account_limit is not None:
        consume(db, scope + ":email", email.lower(), account_limit, seconds)
