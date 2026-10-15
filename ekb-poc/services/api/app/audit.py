"""Append-only audit trail. Every workflow action and every LLM call lands here."""

import logging
from typing import Any

from .db import execute, jsonb

log = logging.getLogger("ekb.audit")


def audit(actor: str, action: str, object_ref: str | None = None, details: dict[str, Any] | None = None) -> None:
    try:
        execute(
            "INSERT INTO audit_log (actor, action, object_ref, details) VALUES (%s, %s, %s, %s)",
            (actor, action, object_ref, jsonb(details or {})),
        )
    except Exception:  # audit must never take the request down, but it must be visible
        log.exception("audit write failed: %s %s %s", actor, action, object_ref)
