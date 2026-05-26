"""Matching domain — the in-process seam to the matching engine.

The ranking logic itself lives in the sibling ``hangpost-matching``
package and must NOT be reimplemented here (CLAUDE.md top matter). This
domain is the thin adapter: it builds ``Query`` objects from app data,
calls ``rank()``, and hands results to the recommendations domain for
impression logging.
"""
