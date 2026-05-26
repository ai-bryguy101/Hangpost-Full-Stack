"""Hangpost API — a modular monolith FastAPI service.

Each bounded context lives in its own subpackage (auth, profiles, posts,
hangouts, social, matching, notifications, safety, recommendations,
workers). Cross-domain calls go through service-layer functions, never
through repository imports from another domain. See
``docs/adrs/0001-modular-monolith.md``.
"""

__version__ = "0.1.0"
