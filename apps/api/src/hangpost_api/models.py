"""Aggregate import of every ORM model.

Importing this module registers all tables on ``Base.metadata``. Alembic's
``env.py`` imports it so autogenerate and ``--sql`` see the full schema,
and the app imports it at startup to ensure mappers are configured.
"""

from hangpost_api.auth.models import User
from hangpost_api.hangouts.models import Hangout, HangoutRsvp
from hangpost_api.notifications.models import Notification
from hangpost_api.posts.models import Post, PostMedia
from hangpost_api.profiles.models import Profile, UserLocation
from hangpost_api.recommendations.models import (
    RecommendationImpression,
    RecommendationOutcome,
)
from hangpost_api.safety.models import Report, UserBlock
from hangpost_api.social.models import Friendship, FriendshipImport

__all__ = [
    "Friendship",
    "FriendshipImport",
    "Hangout",
    "HangoutRsvp",
    "Notification",
    "Post",
    "PostMedia",
    "Profile",
    "RecommendationImpression",
    "RecommendationOutcome",
    "Report",
    "User",
    "UserBlock",
    "UserLocation",
]
