"""Recommendations domain — where the ML loop closes.

Owns ``recommendation_impressions`` (every ranked candidate ever
surfaced, with score, model version, and the full breakdown) and
``recommendation_outcomes`` (the downstream user action). Together these
convert the matching engine from "evaluated on synthetic labels" to
"evaluated on real outcomes" (CLAUDE.md §5).
"""
