"""Pydantic models for the recommendation outcome endpoint.

``OutcomeAction`` is an API-layer validation enum (not a PostgreSQL enum
type — the outcomes table stores one boolean/timestamp column per
action, see ``models.RecommendationOutcome``). Each action maps to a
column the endpoint sets; together they are the training labels the ML
loop learns from (CLAUDE.md §5).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class OutcomeAction(StrEnum):
    VIEWED = "viewed"
    PROFILE_OPENED = "profile_opened"
    FRIEND_REQUEST_SENT = "friend_request_sent"
    BLOCKED = "blocked"
    HANGOUT_RSVPED = "hangout_rsvped"


class OutcomeCreate(BaseModel):
    """A single action the viewer took on a surfaced recommendation."""

    action: OutcomeAction


class OutcomeRead(BaseModel):
    """The accumulated outcome row for one impression."""

    model_config = ConfigDict(from_attributes=True)

    impression_id: uuid.UUID
    viewed_at: datetime | None
    profile_opened: bool
    friend_request_sent: bool
    blocked: bool
    hangout_rsvped: bool
    updated_at: datetime
