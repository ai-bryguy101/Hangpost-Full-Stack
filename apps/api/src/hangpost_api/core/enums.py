"""Domain enumerations, mirrored 1:1 with the PostgreSQL enum types.

The PG types are created by the initial Alembic migration. These Python
enums name those existing types (``create_type=False`` at the column),
so SQLAlchemy never tries to re-create them.
"""

from enum import StrEnum


class PostType(StrEnum):
    HANGOUT = "hangout"
    LOCAL_INFO = "local_info"


class PostVisibility(StrEnum):
    MATCHED_ONLY = "matched_only"
    FRIENDS_OF_FRIENDS = "friends_of_friends"
    PUBLIC_IN_AREA = "public_in_area"


class HangoutStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class RsvpStatus(StrEnum):
    INTERESTED = "interested"
    GOING = "going"
    CANCELLED = "cancelled"


class FriendshipState(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ReportStatus(StrEnum):
    OPEN = "open"
    TRIAGING = "triaging"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"


class NotifKind(StrEnum):
    NEW_MATCH = "new_match"
    HANGOUT_INVITE = "hangout_invite"
    RSVP = "rsvp"
    COMMENT = "comment"
    FRIEND_REQUEST = "friend_request"
