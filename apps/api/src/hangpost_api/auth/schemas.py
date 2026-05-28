"""Pydantic models exposed by the auth domain."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class MeRead(BaseModel):
    """Minimal identity snapshot for ``GET /me``.

    Profile fields live on the profiles domain — clients fetch them via
    ``GET /profiles/me`` once that endpoint lands.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    auth_provider: str
    auth_sub: str
    created_at: datetime
