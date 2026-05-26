"""Profiles & current location domain.

Owns ``profiles`` (mirrors ``hangpost_matching.UserProfile`` plus product
fields, including the pgvector embedding) and ``user_locations`` (the
source of truth for the radius pre-filter — see CLAUDE.md §2).
"""
